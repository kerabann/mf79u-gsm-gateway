package main

import (
	"crypto/tls"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"
)

func telegramFixture() TelegramSMS {
	return TelegramSMS{Enabled: true, BotToken: "1234:" + strings.Repeat("x", 30), ChatID: "-1001234", Interface: "bridge0"}
}
func telegramInbox(id, tag string) map[string]any {
	return map[string]any{"id": id, "tag": tag, "number": "+123456789", "date": "26,10,11,12,00,00,+00", "text": "Привет <b>🌍</b>"}
}
func telegramBridgeFixture(t *testing.T) (*telegramSMSBridge, *TelegramSMS, *map[string][]any) {
	t.Helper()
	c := telegramFixture()
	inbox := map[string][]any{"modem": {telegramInbox("17", "1")}, "sim": {}}
	b := &telegramSMSBridge{path: filepath.Join(t.TempDir(), "queue.json"), config: func() TelegramSMS { return c }, list: func(storage string) (map[string]any, error) { return map[string]any{"messages": inbox[storage]}, nil }, send: func(TelegramSMS, smsSIPItem) (time.Duration, error) { return 0, nil }, delete: func(smsSIPItem) error { return nil }}
	return b, &c, &inbox
}

func TestTelegramScopedSettingsAndSecrets(t *testing.T) {
	a := fixtureApp(nil)
	a.dir = t.TempDir()
	a.applied = a.settings
	c := telegramFixture()
	c.DeleteAfterSend = true
	body, _ := json.Marshal(c)
	for _, tc := range []struct {
		auth, csrf bool
		code       int
	}{{false, false, 401}, {true, false, 403}, {true, true, 200}} {
		w := adminRequest(a, "PUT", "/api/webhooks/telegram", string(body), tc.auth, tc.csrf)
		if w.Code != tc.code {
			t.Fatalf("webhook auth: %d", w.Code)
		}
		if strings.Contains(w.Body.String(), c.BotToken) {
			t.Fatal("token disclosed")
		}
	}
	if !reflect.DeepEqual(a.settings.SIP, defaults().SIP) || !a.settings.Webhooks.TelegramSMS.DeleteAfterSend {
		t.Fatal("scoped settings changed SIP or lost deletion flag")
	}
	w := adminRequest(a, "GET", "/api/settings", "", true, false)
	if strings.Contains(w.Body.String(), c.BotToken) || !strings.Contains(w.Body.String(), `"botTokenSet":true`) {
		t.Fatal("public token masking")
	}
	c.BotToken, c.BotTokenSet = "", true
	body, _ = json.Marshal(c)
	if adminRequest(a, "PUT", "/api/webhooks/telegram", string(body), true, true).Code != 200 || a.settings.Webhooks.TelegramSMS.BotToken == "" {
		t.Fatal("masked token was not preserved")
	}
	old := a.settings.Webhooks
	legacy, _ := json.Marshal(defaults())
	if adminRequest(a, "PUT", "/api/settings", string(legacy), true, true).Code != 200 || a.settings.Webhooks != old {
		t.Fatal("legacy full save erased webhook")
	}
	persisted, e := readSettings(a.dir)
	if e != nil || persisted.Webhooks != old {
		t.Fatal("webhook persistence")
	}
	info, _ := os.Stat(filepath.Join(a.dir, "settings.json"))
	if info.Mode().Perm() != 0600 {
		t.Fatal("private settings permissions")
	}
}

func TestTelegramValidation(t *testing.T) {
	if validateTelegram(TelegramSMS{}) != nil || validateTelegram(telegramFixture()) != nil {
		t.Fatal("valid config")
	}
	for _, change := range []func(*TelegramSMS){func(c *TelegramSMS) { c.BotToken = "" }, func(c *TelegramSMS) { c.BotToken = "bad\n" }, func(c *TelegramSMS) { c.ChatID = "0" }, func(c *TelegramSMS) { c.ChatID = "x" }, func(c *TelegramSMS) { c.Interface = "wan5" }, func(c *TelegramSMS) { c.Interface = "bridge0;echo" }, func(c *TelegramSMS) { c.Interface = "" }} {
		c := telegramFixture()
		change(&c)
		if validateTelegram(c) == nil {
			t.Fatal("invalid config accepted")
		}
	}
}

func TestTelegramNewIncomingDedupeRestartAndDisabled(t *testing.T) {
	b, c, inbox := telegramBridgeFixture(t)
	sends := 0
	b.send = func(config TelegramSMS, item smsSIPItem) (time.Duration, error) {
		sends++
		if item.Number != "+123456789" || item.Text != "Привет <b>🌍</b>" {
			t.Fatal("Unicode payload altered")
		}
		return 0, nil
	}
	b.tick()
	if sends != 0 {
		t.Fatal("old inbox exported")
	}
	(*inbox)["modem"] = append((*inbox)["modem"], telegramInbox("18", "1"), telegramInbox("19", "2"), telegramInbox("20", "4"))
	b.tick()
	b.tick()
	if sends != 1 || b.state.Delivered != 1 {
		t.Fatal("incoming filtering/dedupe")
	}
	(*inbox)["modem"][1].(map[string]any)["tag"] = "0"
	b.tick()
	if sends != 1 {
		t.Fatal("read tag replayed")
	}
	reloaded := &telegramSMSBridge{path: b.path, config: b.config, list: b.list, send: b.send, delete: b.delete}
	if reloaded.load() != nil {
		t.Fatal("restart load")
	}
	reloaded.tick()
	if sends != 1 {
		t.Fatal("restart replayed")
	}
	c.Enabled = false
	(*inbox)["sim"] = []any{telegramInbox("21", "1")}
	b.tick()
	c.Enabled = true
	b.tick()
	if sends != 1 {
		t.Fatal("disabled period exported")
	}
	c.ChatID = "-1005678"
	b.tick()
	if sends != 1 {
		t.Fatal("new destination exported old inbox")
	}
	info, _ := os.Stat(b.path)
	if info.Mode().Perm() != 0600 {
		t.Fatal("queue permissions")
	}
	a := &App{telegram: b}
	status, _ := json.Marshal(a.telegramStatus())
	if strings.Contains(string(status), "123456789") || strings.Contains(string(status), "Привет") {
		t.Fatal("private status data")
	}
}

func TestTelegramDeliveryDeleteRetryAndRestart(t *testing.T) {
	b, c, inbox := telegramBridgeFixture(t)
	c.DeleteAfterSend = true
	b.tick()
	(*inbox)["modem"] = append((*inbox)["modem"], telegramInbox("18", "1"))
	sends, deletes := 0, 0
	b.send = func(TelegramSMS, smsSIPItem) (time.Duration, error) {
		sends++
		return 0, errors.New("Telegram unavailable")
	}
	b.delete = func(item smsSIPItem) error {
		deletes++
		if item.SourceID != "18" || item.Storage != "modem" {
			t.Fatal("wrong deletion target")
		}
		return errors.New("delete failed")
	}
	b.tick()
	if deletes != 0 || len(b.state.Jobs) != 1 || b.state.Jobs[0].Sent {
		t.Fatal("deleted before confirmation")
	}
	b.nextTry = time.Time{}
	b.send = func(TelegramSMS, smsSIPItem) (time.Duration, error) { sends++; return 0, nil }
	b.tick()
	if sends != 2 || deletes != 1 || !b.state.Jobs[0].Sent || b.state.Delivered != 1 {
		t.Fatal("durable confirmation/deletion retry")
	}
	reloaded := &telegramSMSBridge{path: b.path, config: b.config, list: b.list, send: b.send, delete: b.delete}
	if reloaded.load() != nil {
		t.Fatal("load")
	}
	reloaded.delete = func(smsSIPItem) error { deletes++; return nil }
	reloaded.tick()
	if sends != 2 || deletes != 2 || len(reloaded.state.Jobs) != 0 {
		t.Fatal("delete retry resent confirmed SMS")
	}
}

func TestTelegramDeleteProtectsReusedIDAndMissingInbox(t *testing.T) {
	b, c, inbox := telegramBridgeFixture(t)
	c.DeleteAfterSend = true
	b.tick()
	(*inbox)["modem"] = append((*inbox)["modem"], telegramInbox("18", "1"))
	b.delete = func(smsSIPItem) error { return errors.New("unavailable") }
	b.tick()
	deletes := 0
	b.delete = func(smsSIPItem) error { deletes++; return nil }
	b.nextTry = time.Time{}
	(*inbox)["modem"][1].(map[string]any)["text"] = "Different new SMS with reused ID"
	b.tick()
	if deletes != 0 {
		t.Fatal("deleted reused ID")
	}
	// The changed message is a separate queued item. Delivery cannot make an
	// unavailable inbox look empty and thereby skip deletion confirmation.
	b.list = func(string) (map[string]any, error) { return nil, errors.New("secret failure") }
	b.tick()
	if len(b.state.Jobs) != 1 || !b.state.Jobs[0].Sent || deletes != 0 || strings.Contains(b.lastError, "secret") {
		t.Fatal("failed inbox treated as empty or leaked error")
	}
}

func TestTelegramQueueSaveFailureAndCapacity(t *testing.T) {
	b, c, _ := telegramBridgeFixture(t)
	items := []smsSIPItem{{ID: smsSIPHash("old")}}
	if b.observe(*c, items) != nil {
		t.Fatal("baseline")
	}
	for i := 0; i < telegramQueueLimit+1; i++ {
		items = append(items, smsSIPItem{ID: smsSIPHash(string(rune(i)))})
	}
	if b.observe(*c, items) == nil || len(b.state.Jobs) != telegramQueueLimit {
		t.Fatal("queue overflow silently dropped")
	}
	b.path = filepath.Join(b.path, "impossible")
	prior := b.state
	if b.observe(*c, nil) == nil || !reflect.DeepEqual(prior, b.state) {
		t.Fatal("unpersisted state advanced")
	}
}

func TestTelegramFullQueueStillDeletesConfirmedHead(t *testing.T) {
	b, c, inbox := telegramBridgeFixture(t)
	c.DeleteAfterSend = true
	b.tick()
	for i := 0; i <= telegramQueueLimit; i++ {
		(*inbox)["modem"] = append((*inbox)["modem"], telegramInbox(fmt.Sprint(100+i), "1"))
	}
	deletes := 0
	b.delete = func(smsSIPItem) error { deletes++; return nil }
	b.tick()
	if deletes != 1 || len(b.state.Jobs) != telegramQueueLimit-1 {
		t.Fatal("full queue prevented deletion/drain of a confirmed head")
	}
}

func TestTelegramHTTPSFormatErrorsRateLimitAndTLS(t *testing.T) {
	c := telegramFixture()
	item := smsSIPItem{Number: "+123456789", Text: "Привет <b>🌍</b>"}
	mode := 0
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/bot"+c.BotToken+"/sendMessage" || r.Method != "POST" {
			t.Error("wrong Telegram request")
		}
		var payload map[string]any
		json.NewDecoder(r.Body).Decode(&payload)
		if payload["text"] != item.Number+"\n"+item.Text || payload["chat_id"] != c.ChatID || payload["parse_mode"] != nil {
			t.Error("plain sender/newline/text format")
		}
		switch mode {
		case 0:
			io.WriteString(w, `{"ok":true}`)
		case 1:
			w.WriteHeader(429)
			io.WriteString(w, `{"ok":false,"parameters":{"retry_after":60}}`)
		case 2:
			w.WriteHeader(403)
			io.WriteString(w, `{"ok":false,"description":"private body"}`)
		default:
			io.WriteString(w, `{"ok":false}`)
		}
	}))
	defer server.Close()
	if _, e := telegramRequest(server.Client(), server.URL, c, item); e != nil {
		t.Fatal(e)
	}
	mode = 1
	delay, e := telegramRequest(server.Client(), server.URL, c, item)
	if delay != time.Minute || e == nil {
		t.Fatal("rate limit")
	}
	for _, modeValue := range []int{2, 3} {
		mode = modeValue
		_, e = telegramRequest(server.Client(), server.URL, c, item)
		if e == nil || strings.Contains(e.Error(), c.BotToken) || strings.Contains(e.Error(), "private") {
			t.Fatal("rejection/error secrecy")
		}
	}
	client := &http.Client{Transport: &http.Transport{TLSClientConfig: &tls.Config{MinVersion: tls.VersionTLS12}}}
	defer client.CloseIdleConnections()
	if _, e = telegramRequest(client, server.URL, c, item); e == nil || strings.Contains(e.Error(), c.BotToken) {
		t.Fatal("untrusted TLS or token-bearing error")
	}
}
