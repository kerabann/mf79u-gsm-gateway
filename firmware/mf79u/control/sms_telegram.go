package main

import (
	"bytes"
	"context"
	"crypto/tls"
	"crypto/x509"
	_ "embed"
	"encoding/json"
	"errors"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"sort"
	"sync"
	"syscall"
	"time"
)

type Webhooks struct {
	TelegramSMS TelegramSMS `json:"telegramSMS"`
}
type TelegramSMS struct {
	Enabled         bool   `json:"enabled"`
	BotToken        string `json:"botToken,omitempty"`
	BotTokenSet     bool   `json:"botTokenSet,omitempty"`
	ChatID          string `json:"chatId"`
	Interface       string `json:"interface"`
	DeleteAfterSend bool   `json:"deleteAfterSend"`
}

var telegramTokenRE = regexp.MustCompile(`^[0-9]{1,20}:[A-Za-z0-9_-]{20,128}$`)
var telegramChatRE = regexp.MustCompile(`^-?[1-9][0-9]{0,19}$|^@[A-Za-z][A-Za-z0-9_]{4,31}$`)
var telegramInterfaceRE = regexp.MustCompile(`^(bridge0|wlan0-vxd|wan[0-9])$`)

// The stock B03 CA store lacks the current Telegram chain's public root.
// Embed the official CA root, not a rotating api.telegram.org leaf certificate.
//
//go:embed certs/godaddy-g2.crt
var telegramPublicRoot []byte

var telegramRootOnce sync.Once
var telegramRoots *x509.CertPool

func telegramRootPool() *x509.CertPool {
	telegramRootOnce.Do(func() {
		var e error
		telegramRoots, e = x509.SystemCertPool()
		if e != nil {
			telegramRoots = x509.NewCertPool()
		}
		telegramRoots.AppendCertsFromPEM(telegramPublicRoot)
	})
	return telegramRoots
}

func validateTelegram(c TelegramSMS) error {
	if c.BotToken != "" && !telegramTokenRE.MatchString(c.BotToken) {
		return errors.New("Invalid Telegram bot token")
	}
	if c.ChatID != "" && !telegramChatRE.MatchString(c.ChatID) {
		return errors.New("Enter a numeric Telegram chat ID or @channel username")
	}
	if c.Interface != "" && (!telegramInterfaceRE.MatchString(c.Interface) || c.Interface == "wan5") {
		return errors.New("Choose USB, Wi-Fi client or a mobile data interface")
	}
	if c.Enabled && (c.BotToken == "" || c.ChatID == "" || c.Interface == "") {
		return errors.New("Set the bot token, chat ID and interface before enabling Telegram SMS")
	}
	return nil
}

func (a *App) telegramSettings(w http.ResponseWriter, r *http.Request) {
	if r.Method != "PUT" {
		w.WriteHeader(405)
		return
	}
	var c TelegramSMS
	if e := decode(w, r, &c); e != nil {
		failure(w, 400, e)
		return
	}
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.pending != "" {
		failure(w, 409, errors.New("Confirm or roll back the network changes first"))
		return
	}
	if c.BotToken == "" && c.BotTokenSet {
		c.BotToken = a.settings.Webhooks.TelegramSMS.BotToken
	}
	c.BotTokenSet = false
	if e := validateTelegram(c); e != nil {
		failure(w, 400, e)
		return
	}
	value := a.settings
	value.Webhooks.TelegramSMS = c
	b, _ := json.MarshalIndent(value, "", "  ")
	if e := atomicFile(filepath.Join(a.dir, "settings.json"), b, 0600); e != nil {
		failure(w, 500, errors.New("Could not save webhook settings"))
		return
	}
	a.settings = value
	a.applied.Webhooks = value.Webhooks
	respond(w, 200, map[string]any{"saved": true, "settings": publicSettings(value)})
}

const telegramQueueLimit = 128

// Only private userdata contains queued bodies. Status exposes counts/errors.
// Seen includes incoming IDs in the current inbox, independent of read tags.
type telegramSMSState struct {
	Destination string
	Seen        []string
	Jobs        []telegramSMSJob
	Delivered   uint64
}
type telegramSMSJob struct {
	smsSIPItem
	Sent   bool
	Delete bool
}
type telegramSMSBridge struct {
	mu           sync.Mutex
	path         string
	state        telegramSMSState
	lastError    string
	nextTry      time.Time
	config       func() TelegramSMS
	list         func(string) (map[string]any, error)
	send         func(TelegramSMS, smsSIPItem) (time.Duration, error)
	delete       func(smsSIPItem) error
	retainForSIP func(smsSIPItem) error
}

func (b *telegramSMSBridge) load() error {
	data, e := os.ReadFile(b.path)
	if os.IsNotExist(e) {
		return nil
	}
	if e != nil || len(data) > 600000 || json.Unmarshal(data, &b.state) != nil || len(b.state.Jobs) > telegramQueueLimit || len(b.state.Seen) > 1024 {
		return errors.New("Could not read Telegram SMS queue")
	}
	return nil
}

func (b *telegramSMSBridge) persist(s telegramSMSState) error {
	data, _ := json.Marshal(s)
	if e := atomicFile(b.path, data, 0600); e != nil {
		return errors.New("Could not save Telegram SMS queue")
	}
	b.state = s
	return nil
}

func (b *telegramSMSBridge) observe(c TelegramSMS, items []smsSIPItem) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	next := b.state
	destination := smsSIPHash(c.ChatID)
	baseline := next.Destination != destination
	if baseline {
		// First configuration/new destination never exports the old inbox.
		next = telegramSMSState{Destination: destination}
		b.nextTry = time.Time{}
	}
	known := make(map[string]bool)
	for _, id := range next.Seen {
		known[id] = true
	}
	// Prune disappeared entries, but retain pending jobs after inbox deletion.
	seen := make(map[string]bool)
	for _, job := range next.Jobs {
		seen[job.ID] = true
	}
	next.Jobs = append([]telegramSMSJob(nil), next.Jobs...)
	full := false
	for _, item := range items {
		if !known[item.ID] && !baseline && c.Enabled {
			if len(next.Jobs) >= telegramQueueLimit {
				full = true
				continue // Not marked seen: a later poll can enqueue it.
			}
			next.Jobs = append(next.Jobs, telegramSMSJob{smsSIPItem: item})
		}
		seen[item.ID] = true
		known[item.ID] = true
	}
	next.Seen = make([]string, 0, len(seen))
	for id := range seen {
		next.Seen = append(next.Seen, id)
	}
	sort.Strings(next.Seen)
	if !reflect.DeepEqual(next, b.state) {
		if e := b.persist(next); e != nil {
			return e
		}
	}
	if full {
		return errors.New("Telegram SMS queue is full; waiting for delivery")
	}
	return nil
}

func (b *telegramSMSBridge) tick() {
	c := b.config()
	if c.ChatID == "" {
		return
	}
	items, inboxError := incomingSMS(b.list)
	e := inboxError
	if e == nil {
		e = b.observe(c, items)
	}
	b.mu.Lock()
	if e != nil {
		b.lastError = "Could not read incoming SMS"
		if len(items) > 0 {
			b.lastError = e.Error()
		}
	} else if len(b.state.Jobs) == 0 {
		b.lastError = ""
	}
	// A failed inbox query keeps the durable queue; a destination change must
	// first establish its baseline before any existing job can be sent there.
	if !c.Enabled || b.state.Destination != smsSIPHash(c.ChatID) || len(b.state.Jobs) == 0 || time.Now().Before(b.nextTry) {
		b.mu.Unlock()
		return
	}
	job := b.state.Jobs[0]
	b.mu.Unlock()
	var delay time.Duration
	var sendError error
	if !job.Sent {
		delay, sendError = b.send(c, job.smsSIPItem)
		if sendError == nil {
			job.Sent, job.Delete = true, c.DeleteAfterSend
			b.mu.Lock()
			next := b.state
			next.Jobs = append([]telegramSMSJob(nil), next.Jobs...)
			next.Jobs[0] = job
			next.Delivered++
			sendError = b.persist(next)
			b.mu.Unlock()
		}
	}
	if sendError == nil && job.Delete {
		if inboxError != nil {
			sendError = errors.New("Could not verify SMS before deletion")
		} else {
			// Reused vendor IDs are not permission to delete a different SMS.
			for _, item := range items {
				if item.ID == job.ID {
					if b.retainForSIP != nil {
						sendError = b.retainForSIP(item)
						if sendError != nil {
							break
						}
					}
					if b.delete(item) != nil {
						sendError = errors.New("Telegram delivered; SMS deletion failed, waiting to retry")
					}
					break
				}
			}
		}
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	if sendError != nil {
		b.lastError = sendError.Error()
		if delay < 15*time.Second {
			delay = 15 * time.Second
		}
		if delay > 24*time.Hour {
			delay = 24 * time.Hour
		}
		b.nextTry = time.Now().Add(delay)
		return
	}
	next := b.state
	next.Jobs = append([]telegramSMSJob(nil), next.Jobs[1:]...)
	if e := b.persist(next); e != nil {
		b.lastError = e.Error()
		b.nextTry = time.Now().Add(time.Minute)
		return
	}
	b.lastError = ""
	b.nextTry = time.Time{}
}

func (a *App) telegramStatus() map[string]any {
	if a.telegram == nil {
		return map[string]any{"running": false}
	}
	b := a.telegram
	b.mu.Lock()
	defer b.mu.Unlock()
	return map[string]any{"running": true, "initialized": b.state.Destination != "", "queued": len(b.state.Jobs), "delivered": b.state.Delivered, "error": b.lastError}
}

func (a *App) startTelegramSMS() error {
	b := &telegramSMSBridge{path: filepath.Join(a.dir, "sms-telegram-state.json")}
	b.config = func() TelegramSMS { a.mu.Lock(); defer a.mu.Unlock(); return a.settings.Webhooks.TelegramSMS }
	b.list = func(storage string) (map[string]any, error) {
		v, key, e := a.localSMSVendor()
		if e != nil {
			return nil, e
		}
		return a.smsList(v, storage, key)
	}
	b.send = sendTelegramSMS
	b.retainForSIP = func(item smsSIPItem) error {
		if a.smsSIP != nil {
			return a.smsSIP.retainIncoming(item)
		}
		a.mu.Lock()
		s := a.settings.SIP
		a.mu.Unlock()
		if sipSMSPeerAvailable(s, gatewayStatus()) {
			return errors.New("Telegram delivered; SIP SMS service unavailable, waiting before SMS deletion")
		}
		return nil
	}
	b.delete = func(item smsSIPItem) error {
		v, key, e := a.localSMSVendor()
		if e != nil {
			return e
		}
		return a.smsAction(v, "delete", []string{item.SourceID}, "", "", key)
	}
	if e := b.load(); e != nil {
		return e
	}
	a.telegram = b
	go func() {
		ticker := time.NewTicker(5 * time.Second)
		defer ticker.Stop()
		for {
			b.tick()
			<-ticker.C
		}
	}()
	return nil
}

func telegramDialer(iface string) *net.Dialer {
	control := func(_, _ string, c syscall.RawConn) error { return bindTelegramInterface(c, iface) }
	// Bind DNS and HTTPS independently. No proxy, redirect or alternate uplink.
	dnsDialer := &net.Dialer{Timeout: 5 * time.Second, Control: control}
	resolver := &net.Resolver{PreferGo: true, Dial: func(ctx context.Context, network, address string) (net.Conn, error) {
		return dnsDialer.DialContext(ctx, network, address)
	}}
	return &net.Dialer{Timeout: 10 * time.Second, Resolver: resolver, Control: control}
}

func telegramClient(iface string) *http.Client {
	dialer := telegramDialer(iface)
	transport := &http.Transport{DialContext: dialer.DialContext, TLSClientConfig: &tls.Config{RootCAs: telegramRootPool(), MinVersion: tls.VersionTLS12}, TLSHandshakeTimeout: 10 * time.Second, DisableKeepAlives: true, MaxResponseHeaderBytes: 8192}
	return &http.Client{Transport: transport, Timeout: 20 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return errors.New("Telegram redirect refused") }}
}

func sendTelegramSMS(c TelegramSMS, item smsSIPItem) (time.Duration, error) {
	if e := validateTelegram(c); e != nil {
		return 0, e
	}
	iface, e := interfaceByName(c.Interface)
	if e != nil || iface.Flags&net.FlagUp == 0 {
		return 0, errors.New("Telegram interface is unavailable")
	}
	client := telegramClient(c.Interface)
	defer client.CloseIdleConnections()
	return telegramRequest(client, "https://api.telegram.org", c, item)
}

// The production URL is fixed. Tests use a local TLS fixture with fake inputs.
func telegramRequest(client *http.Client, base string, c TelegramSMS, item smsSIPItem) (time.Duration, error) {
	body, _ := json.Marshal(map[string]any{"chat_id": c.ChatID, "text": item.Number + "\n" + item.Text, "link_preview_options": map[string]bool{"is_disabled": true}})
	r, e := client.Post(base+"/bot"+c.BotToken+"/sendMessage", "application/json", bytes.NewReader(body))
	if e != nil {
		// net/http errors contain the token-bearing URL. Never expose them.
		if category := telegramErrorCategory(e); category == "tls_untrusted_root" || category == "tls_invalid_certificate" || category == "tls_hostname_mismatch" {
			return 0, errors.New("Telegram TLS certificate verification failed; check device time and trusted CA roots")
		}
		return 0, errors.New("Telegram HTTPS request failed; check interface, internet, DNS and device time")
	}
	defer r.Body.Close()
	var reply struct {
		OK         bool `json:"ok"`
		Parameters struct {
			RetryAfter int `json:"retry_after"`
		} `json:"parameters"`
	}
	if e := json.NewDecoder(io.LimitReader(r.Body, 65536)).Decode(&reply); e != nil {
		return 0, errors.New("Invalid Telegram response")
	}
	if r.StatusCode == 200 && reply.OK {
		return 0, nil
	}
	if r.StatusCode == 429 {
		seconds := reply.Parameters.RetryAfter
		if seconds < 1 {
			seconds = 30
		}
		if seconds > 86400 {
			seconds = 86400
		}
		return time.Duration(seconds) * time.Second, errors.New("Telegram rate limit; waiting to retry")
	}
	return 0, errors.New("Telegram rejected the message; check bot token, chat ID and bot permissions")
}
