package main

// Private, bounded local IPC. SIP authenticates the client; this socket is
// accessible only to device-local privileged services. No new TCP endpoint,
// saved admin credential, external relay, or logging of SMS contents.
import (
	"context"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"
	"unicode/utf8"
)

const smsSIPLimit = 64

type smsSIPJob struct {
	ID, Hash, Number, Text, State string
}
type smsSIPState struct {
	Jobs      []smsSIPJob
	Delivered []string
	Inbox     []smsSIPItem `json:",omitempty"`
}
type smsSIPItem struct{ ID, Number, Text, Date, Storage, SourceID string }
type smsSIPBridge struct {
	mu        sync.Mutex
	state     smsSIPState
	incoming  []smsSIPItem
	ready     bool
	path      string
	wake      chan struct{}
	enabled   func() bool
	connected func() bool
	list      func(string) (map[string]any, error)
	send      func(string, string) error
}

func smsSIPHash(value string) string {
	h := sha256.Sum256([]byte(value))
	return hex.EncodeToString(h[:16])
}
func smsSIPKey() (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	// B03 stores the SHA256 administrator verifier already; keep it in RAM.
	b, e := exec.CommandContext(ctx, "/bin/cfg", "get", "admin_Password").Output()
	key := strings.ToUpper(strings.TrimSpace(string(b)))
	decoded, x := hex.DecodeString(key)
	if e != nil || x != nil || len(decoded) != 32 {
		return "", errors.New("Local SMS authentication unavailable")
	}
	return key, nil
}
func (a *App) localSMSVendor() (*Vendor, string, error) {
	key, e := smsSIPKey()
	if e != nil {
		return nil, "", e
	}
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.vendorClient == nil {
		a.vendorClient = vendor(a.base)
	}
	return a.vendorClient, key, nil
}
func (b *smsSIPBridge) saveLocked() error {
	data, e := json.Marshal(b.state)
	if e != nil {
		return e
	}
	return atomicFile(b.path, data, 0600)
}
func (b *smsSIPBridge) load() error {
	data, e := os.ReadFile(b.path)
	if os.IsNotExist(e) {
		return nil
	}
	if e != nil || len(data) > 600000 || json.Unmarshal(data, &b.state) != nil || len(b.state.Jobs) > smsSIPLimit || len(b.state.Inbox) > smsSIPLimit || len(b.state.Delivered) > 300 {
		return errors.New("Invalid SMS SIP queue")
	}
	for i := range b.state.Jobs {
		if b.state.Jobs[i].State == "sending" {
			// A reboot after SEND_SMS has an ambiguous result. Never send again.
			b.state.Jobs[i].State = "uncertain"
			b.state.Jobs[i].Text = ""
		}
	}
	return b.saveLocked()
}
func (b *smsSIPBridge) enqueue(id, number, text string) byte {
	if !b.enabled() {
		return 2
	}
	decoded, e := hex.DecodeString(id)
	if e != nil || len(decoded) != 16 || !numberRE.MatchString(number) || !utf8.ValidString(text) || strings.ContainsRune(text, 0) || len([]rune(text)) < 1 || len([]rune(text)) > 670 {
		return 1
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	hash := smsSIPHash(number + "\x00" + text)
	for _, j := range b.state.Jobs {
		if j.ID == id {
			if j.Hash != hash {
				return 4 // Same transaction identity, different payload.
			}
			return 0
		}
	}
	old := append([]smsSIPJob(nil), b.state.Jobs...)
	if len(b.state.Jobs) == smsSIPLimit {
		first := b.state.Jobs[0]
		if first.State == "queued" || first.State == "sending" {
			return 3
		}
		b.state.Jobs = append([]smsSIPJob(nil), b.state.Jobs[1:]...)
	}
	b.state.Jobs = append(b.state.Jobs, smsSIPJob{ID: id, Hash: hash, Number: number, Text: text, State: "queued"})
	if b.saveLocked() != nil {
		b.state.Jobs = old
		return 2
	}
	select {
	case b.wake <- struct{}{}:
	default:
	}
	return 0
}

// Status is read-only: polling a completed or ambiguous job never resubmits it.
func (b *smsSIPBridge) submission(id string) byte {
	b.mu.Lock()
	defer b.mu.Unlock()
	for _, j := range b.state.Jobs {
		if j.ID == id {
			switch j.State {
			case "queued", "sending":
				return 5
			case "sent":
				return 0
			default:
				return 6
			}
		}
	}
	return 2
}
func (b *smsSIPBridge) deliveredLocked(id string) bool {
	for _, known := range b.state.Delivered {
		if known == id {
			return true
		}
	}
	return false
}

// Preserve a private SIP copy before Telegram deletes the original inbox SMS.
// A connected peer may disappear while MESSAGE is in flight; retain until ACK.
func (b *smsSIPBridge) retainIncoming(item smsSIPItem) error {
	if !b.enabled() {
		return nil
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.deliveredLocked(item.ID) {
		return nil
	}
	for _, known := range b.state.Inbox {
		if known.ID == item.ID {
			return nil
		}
	}
	if !b.connected() {
		return nil
	}
	if len(b.state.Inbox) >= smsSIPLimit {
		return errors.New("Telegram delivered; SIP inbox queue is full, waiting before SMS deletion")
	}
	old := b.state.Inbox
	b.state.Inbox = append(append([]smsSIPItem(nil), old...), item)
	if b.saveLocked() != nil {
		b.state.Inbox = old
		return errors.New("Telegram delivered; could not save SIP copy, waiting before SMS deletion")
	}
	return nil
}

func sipSMSPeerAvailable(s SIP, status map[string]any) bool {
	if status["running"] != true || status["role"] != s.Role {
		return false
	}
	switch s.Role {
	case "SERVER":
		return status["localRegistered"] == true
	case "TRUNK":
		return !s.Register || status["registered"] == true
	default:
		return false
	}
}

func (b *smsSIPBridge) next() *smsSIPItem {
	if !b.enabled() {
		return nil
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	for _, item := range b.state.Inbox {
		if !b.deliveredLocked(item.ID) {
			copy := item
			return &copy
		}
	}
	for _, item := range b.incoming {
		if !b.deliveredLocked(item.ID) {
			copy := item
			return &copy
		}
	}
	for _, j := range b.state.Jobs {
		id := smsSIPHash("status:" + j.ID)
		if (j.State == "failed" || j.State == "uncertain") && !b.deliveredLocked(id) {
			text := "MF79U status: the modem reported an SMS submission error. The recipient may still receive it. Check delivery before sending again."
			if j.State == "uncertain" {
				text = "MF79U status: SMS submission is unconfirmed by the modem API. The recipient may still receive it. Check delivery before sending again."
			}
			// A local service notice must not impersonate the SMS recipient.
			return &smsSIPItem{ID: id, Number: "MF79U", Text: text}
		}
	}
	return nil
}
func (b *smsSIPBridge) ack(id string) byte {
	decoded, e := hex.DecodeString(id)
	if e != nil || len(decoded) != 16 {
		return 1
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.deliveredLocked(id) {
		return 0
	}
	// The local gateway may ack after the user deletes the underlying SMS.
	old := b.state
	b.state.Delivered = append(b.state.Delivered, id)
	if len(b.state.Delivered) > 300 {
		b.state.Delivered = b.state.Delivered[len(b.state.Delivered)-300:]
	}
	b.state.Inbox = nil
	for _, item := range old.Inbox {
		if item.ID != id {
			b.state.Inbox = append(b.state.Inbox, item)
		}
	}
	if b.saveLocked() != nil {
		b.state = old
		return 2
	}
	return 0
}
func (b *smsSIPBridge) processOne() bool {
	if !b.enabled() {
		return false
	}
	b.mu.Lock()
	index := -1
	for i, job := range b.state.Jobs {
		if job.State == "queued" {
			index = i
			break
		}
	}
	if index < 0 {
		b.mu.Unlock()
		return false
	}
	job := b.state.Jobs[index]
	b.state.Jobs[index].State = "sending"
	if b.saveLocked() != nil {
		b.state.Jobs[index].State = "queued"
		b.mu.Unlock()
		return false
	}
	b.mu.Unlock()
	e := b.send(job.Number, job.Text)
	b.mu.Lock()
	defer b.mu.Unlock()
	// Entries cannot be evicted while sending; identify by ID anyway.
	for i := range b.state.Jobs {
		if b.state.Jobs[i].ID == job.ID {
			state := "sent"
			if e != nil {
				state = "uncertain" // Vendor timeouts may follow an actual send.
			}
			b.state.Jobs[i].State, b.state.Jobs[i].Text = state, ""
			// Failed persistence retains on-disk 'sending', hence no replay on reboot.
			_ = b.saveLocked()
			break
		}
	}
	return true
}
func (b *smsSIPBridge) refresh() {
	if !b.enabled() {
		return
	}
	items, e := incomingSMS(b.list)
	b.mu.Lock()
	defer b.mu.Unlock()
	if e != nil {
		b.ready = false
		return // Preserve the cache on failure, never invent an empty inbox.
	}
	b.incoming = items
	b.ready = true
}

func incomingSMS(list func(string) (map[string]any, error)) ([]smsSIPItem, error) {
	items := []smsSIPItem{}
	for _, storage := range []string{"modem", "sim"} {
		value, e := list(storage)
		if e != nil {
			return nil, errors.New("Could not read incoming SMS")
		}
		messages, ok := value["messages"].([]any)
		if !ok || len(messages) > 328 {
			return nil, errors.New("Invalid incoming SMS list")
		}
		for _, raw := range messages {
			m, ok := raw.(map[string]any)
			if !ok || smsDirection(str(m["tag"])) != "incoming" {
				continue
			}
			number, text := smsNumber(str(m["number"])), str(m["text"])
			if number == "" || len(number) > 128 || strings.ContainsAny(number, "\x00\r\n") || !utf8.ValidString(text) || strings.ContainsRune(text, 0) || len([]rune(text)) < 1 || len([]rune(text)) > 670 {
				continue
			}
			date := str(m["date"])
			key := smsSIPHash(storage + "\x00" + str(m["id"]) + "\x00" + number + "\x00" + date + "\x00" + text)
			when := ""
			if normalized := smsDate(date); normalized != nil {
				when = *normalized
			}
			items = append(items, smsSIPItem{ID: key, Number: number, Text: text, Date: when, Storage: storage, SourceID: str(m["id"])})
		}
	}
	sort.SliceStable(items, func(i, j int) bool { return items[i].Date < items[j].Date })
	return items, nil
}
func (b *smsSIPBridge) worker() {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()
	b.refresh()
	lastRefresh := time.Now()
	for {
		if time.Since(lastRefresh) >= 5*time.Second {
			b.refresh()
			lastRefresh = time.Now()
		}
		if b.processOne() {
			continue
		}
		select {
		case <-ticker.C:
		case <-b.wake:
		}
	}
}

// Frame: MSM1, opcode/status byte, big-endian uint32 payload size.
// 1=enqueue (32-byte hex ID + two uint16 lengths + number/text), 2=next,
// 3=ack (32-byte ID). Reply 0=ok, 1=invalid, 2=unavailable, 3=full, 4=conflict.
func (b *smsSIPBridge) connection(c net.Conn) {
	defer c.Close()
	_ = c.SetDeadline(time.Now().Add(500 * time.Millisecond))
	header := make([]byte, 9)
	if _, e := io.ReadFull(c, header); e != nil || string(header[:4]) != "MSM1" {
		return
	}
	n := binary.BigEndian.Uint32(header[5:])
	if n > 8192 {
		return
	}
	payload := make([]byte, n)
	if _, e := io.ReadFull(c, payload); e != nil {
		return
	}
	status, body := byte(1), []byte(nil)
	switch header[4] {
	case 1:
		if len(payload) >= 36 {
			a, z := int(binary.BigEndian.Uint16(payload[32:34])), int(binary.BigEndian.Uint16(payload[34:36]))
			if 36+a+z == len(payload) {
				status = b.enqueue(string(payload[:32]), string(payload[36:36+a]), string(payload[36+a:]))
			}
		}
	case 2:
		if n == 0 {
			status = 0
			if item := b.next(); item != nil {
				body = make([]byte, 38)
				copy(body, item.ID)
				binary.BigEndian.PutUint16(body[32:34], uint16(len(item.Number)))
				binary.BigEndian.PutUint16(body[34:36], uint16(len(item.Text)))
				binary.BigEndian.PutUint16(body[36:38], uint16(len(item.Date)))
				body = append(body, []byte(item.Number+item.Text+item.Date)...)
			}
		}
	case 3:
		if n == 32 {
			status = b.ack(string(payload))
		}
	case 5: // Read-only outgoing submission result: 5=pending, 6=unconfirmed.
		if n == 32 {
			status = b.submission(string(payload))
		}
	case 4: // Diagnostics contain only counters/flags, never message fields.
		if n == 0 {
			enabled := b.enabled()
			b.mu.Lock()
			queued := 0
			pending := make(map[string]bool)
			for _, j := range b.state.Jobs {
				if j.State == "queued" || j.State == "sending" {
					queued++
				}
			}
			for _, item := range b.incoming {
				if !b.deliveredLocked(item.ID) {
					pending[item.ID] = true
				}
			}
			for _, item := range b.state.Inbox {
				if !b.deliveredLocked(item.ID) {
					pending[item.ID] = true
				}
			}
			body, _ = json.Marshal(map[string]any{"enabled": enabled, "vendorReady": b.ready, "queued": queued,
				"incoming": len(b.incoming), "pendingIncoming": len(pending), "bufferedIncoming": len(b.state.Inbox), "delivered": len(b.state.Delivered)})
			b.mu.Unlock()
			status = 0
		}
	}
	copy(header, "MSM1")
	header[4] = status
	binary.BigEndian.PutUint32(header[5:], uint32(len(body)))
	_, _ = c.Write(append(header, body...))
}
func (a *App) startSMSSIP() error {
	path := filepath.Join(a.dir, "sms-sip.sock")
	if _, e := os.Lstat(path); e == nil {
		c, e := net.DialTimeout("unix", path, 100*time.Millisecond)
		if e == nil {
			c.Close()
			return errors.New("SMS SIP socket already owned")
		}
		info, _ := os.Lstat(path)
		if info.Mode()&os.ModeSocket == 0 {
			return errors.New("Invalid SMS SIP socket path")
		}
		if e := os.Remove(path); e != nil {
			return e
		}
	}
	b := &smsSIPBridge{path: filepath.Join(a.dir, "sms-sip-state.json"), wake: make(chan struct{}, 1)}
	b.enabled = func() bool { a.mu.Lock(); defer a.mu.Unlock(); return a.settings.SIP.Role != "DISABLED" }
	b.connected = func() bool {
		a.mu.Lock()
		s := a.settings.SIP
		a.mu.Unlock()
		return sipSMSPeerAvailable(s, gatewayStatus())
	}
	b.list = func(storage string) (map[string]any, error) {
		v, key, e := a.localSMSVendor()
		if e != nil {
			return nil, e
		}
		return a.smsList(v, storage, key)
	}
	b.send = func(number, text string) error {
		v, key, e := a.localSMSVendor()
		if e != nil {
			return e
		}
		return a.smsAction(v, "send", nil, number, text, key)
	}
	if e := b.load(); e != nil {
		return e
	}
	listener, e := net.Listen("unix", path)
	if e != nil {
		return e
	}
	if e = os.Chmod(path, 0600); e != nil {
		listener.Close()
		return e
	}
	a.smsSIP = b
	go b.worker()
	go func() {
		limit := make(chan struct{}, 4)
		for {
			c, e := listener.Accept()
			if e != nil {
				return
			}
			select {
			case limit <- struct{}{}:
				go func() { defer func() { <-limit }(); b.connection(c) }()
			default:
				c.Close()
			}
		}
	}()
	return nil
}
