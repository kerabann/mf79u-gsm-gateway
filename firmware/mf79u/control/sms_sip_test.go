package main

import (
	"encoding/binary"
	"errors"
	"io"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func testSMSBridge(t *testing.T) *smsSIPBridge {
	t.Helper()
	return &smsSIPBridge{path: filepath.Join(t.TempDir(), "queue.json"), wake: make(chan struct{}, 1), enabled: func() bool { return true }, connected: func() bool { return true }}
}

func TestSMSSIPPeerAvailabilityIndependentOfVoice(t *testing.T) {
	for _, tc := range []struct {
		role                                       string
		register, running, local, registered, want bool
	}{
		{"SERVER", false, true, true, false, true},
		{"SERVER", false, true, false, false, false},
		{"SERVER", false, false, true, false, false},
		{"TRUNK", true, true, false, true, true},
		{"TRUNK", true, true, false, false, false},
		{"TRUNK", false, true, false, false, true},
		{"DISABLED", false, true, true, true, false},
	} {
		status := map[string]any{"role": tc.role, "running": tc.running, "localRegistered": tc.local, "registered": tc.registered, "voiceReady": false}
		if sipSMSPeerAvailable(SIP{Role: tc.role, Register: tc.register}, status) != tc.want {
			t.Fatal("incorrect SIP peer availability")
		}
	}
	if sipSMSPeerAvailable(SIP{Role: "SERVER"}, map[string]any{"running": true, "role": "TRUNK", "localRegistered": true}) {
		t.Fatal("stale role accepted")
	}
}

func TestSMSSIPRetainedInboxRestartAckAndBounds(t *testing.T) {
	b := testSMSBridge(t)
	item := smsSIPItem{ID: smsSIPHash("received"), Number: "Sender", Text: "Привет 🌍", SourceID: "ims-fixture", Storage: "modem"}
	if b.retainIncoming(item) != nil || b.retainIncoming(item) != nil || len(b.state.Inbox) != 1 {
		t.Fatal("SIP copy missing or duplicated")
	}
	b.connected = func() bool { return false }
	if b.retainIncoming(item) != nil || len(b.state.Inbox) != 1 {
		t.Fatal("disconnect discarded SIP copy")
	}
	reloaded := testSMSBridge(t)
	reloaded.path = b.path
	reloaded.list = func(string) (map[string]any, error) { return map[string]any{"messages": []any{}}, nil }
	if reloaded.load() != nil {
		t.Fatal("load")
	}
	reloaded.refresh() // Original SMS is already deleted by Telegram.
	if next := reloaded.next(); next == nil || *next != item {
		t.Fatal("retained SMS lost after original deletion/restart")
	}
	path := reloaded.path
	reloaded.path = t.TempDir() // Atomic persistence cannot replace a directory.
	if reloaded.ack(item.ID) != 2 || len(reloaded.state.Inbox) != 1 || reloaded.deliveredLocked(item.ID) {
		t.Fatal("failed ACK persistence discarded copy")
	}
	reloaded.path = path
	if reloaded.ack(item.ID) != 0 || reloaded.next() != nil || len(reloaded.state.Inbox) != 0 {
		t.Fatal("ACK did not erase private copy")
	}
	data, e := os.ReadFile(path)
	if e != nil || strings.Contains(string(data), item.Text) {
		t.Fatal("acknowledged body retained on disk")
	}
	if reloaded.retainIncoming(item) != nil || len(reloaded.state.Inbox) != 0 || reloaded.load() != nil || reloaded.next() != nil {
		t.Fatal("confirmed SMS replayed")
	}
	b = testSMSBridge(t)
	b.connected = func() bool { return false }
	if b.retainIncoming(item) != nil || len(b.state.Inbox) != 0 {
		t.Fatal("offline client created deletion dependency")
	}
	b.connected = func() bool { return true }
	b.enabled = func() bool { return false }
	if b.retainIncoming(item) != nil || len(b.state.Inbox) != 0 {
		t.Fatal("Disabled retained incoming")
	}
	b.enabled = func() bool { return true }
	for i := 0; i < smsSIPLimit; i++ {
		item.ID = smsSIPHash(string(rune(i)))
		if b.retainIncoming(item) != nil {
			t.Fatal("bounded SIP copy rejected")
		}
	}
	item.ID = smsSIPHash("overflow")
	if b.retainIncoming(item) == nil || len(b.state.Inbox) != smsSIPLimit {
		t.Fatal("full copy queue silently lost SMS")
	}
}
func TestSMSSIPDurableDedupeAndUnicode(t *testing.T) {
	b := testSMSBridge(t)
	id := smsSIPHash("sip-transaction")
	text := "Привет, κόσμε 🌍"
	if b.enqueue(id, "+391234567", text) != 0 || b.enqueue(id, "+391234567", text) != 0 || len(b.state.Jobs) != 1 {
		t.Fatal("duplicate SIP request created multiple jobs")
	}
	if b.enqueue(id, "+391234567", "different") != 4 {
		t.Fatal("transaction payload conflict accepted")
	}
	reloaded := testSMSBridge(t)
	reloaded.path = b.path
	if reloaded.load() != nil || reloaded.state.Jobs[0].Text != text {
		t.Fatal("Unicode queued SMS did not survive restart")
	}
	calls := 0
	reloaded.send = func(number, body string) error {
		calls++
		if number != "+391234567" || body != text {
			t.Fatal("SMS fields changed")
		}
		return nil
	}
	if !reloaded.processOne() || reloaded.processOne() || calls != 1 || reloaded.state.Jobs[0].State != "sent" {
		t.Fatal("SMS was not sent exactly once by worker")
	}
	if reloaded.enqueue(id, "+391234567", text) != 0 || reloaded.processOne() {
		t.Fatal("completed SMS replayed")
	}
	info, _ := os.Stat(b.path)
	if info.Mode().Perm() != 0600 {
		t.Fatal("queue permissions")
	}
}
func TestSMSSIPAmbiguousSendNeverRetried(t *testing.T) {
	b := testSMSBridge(t)
	id := smsSIPHash("ambiguous")
	b.state.Jobs = []smsSIPJob{{ID: id, Number: "12345", Text: "private", State: "sending"}}
	if b.saveLocked() != nil {
		t.Fatal("save")
	}
	if b.load() != nil || b.state.Jobs[0].State != "uncertain" || b.state.Jobs[0].Text != "" {
		t.Fatal("crash recovery")
	}
	b.send = func(string, string) error { t.Fatal("ambiguous send retried"); return nil }
	if b.processOne() {
		t.Fatal("replayed interrupted send")
	}
	item := b.next()
	if item == nil || item.Number != "MF79U" || !strings.Contains(item.Text, "unconfirmed by the modem API") || !strings.Contains(item.Text, "recipient may still receive") {
		t.Fatal("missing uncertainty notification")
	}
	if b.ack(item.ID) != 0 || b.next() != nil {
		t.Fatal("notification not acknowledged")
	}
}
func TestSMSSIPIncomingStorageAndAck(t *testing.T) {
	b := testSMSBridge(t)
	b.list = func(storage string) (map[string]any, error) {
		return map[string]any{"messages": []any{
			map[string]any{"id": "1", "number": "00310032003300340035", "text": "Привет", "date": "26,10,8,1,2,3,+12", "tag": "0"},
			map[string]any{"id": "2", "number": "12345", "text": "outgoing", "tag": "2"},
		}}, nil
	}
	b.refresh()
	if len(b.incoming) != 2 || b.incoming[0].Number != "12345" || b.incoming[0].Date != "2026-10-08T01:02:03+03:00" {
		t.Fatal("incoming normalization/storage")
	}
	a, z := b.incoming[0], b.incoming[1]
	if a.ID == z.ID {
		t.Fatal("SIM and modem IDs collided")
	}
	if b.ack(a.ID) != 0 || b.next().ID != z.ID {
		t.Fatal("ack")
	}
	if b.load() != nil || b.next().ID != z.ID {
		t.Fatal("ack did not survive restart")
	}
	b.list = func(string) (map[string]any, error) { return nil, errors.New("expired") }
	b.refresh()
	if b.next().ID != z.ID {
		t.Fatal("API error treated as empty inbox")
	}
	// Deletion between MESSAGE delivery and its 200 reply cannot block all later SMS.
	b.incoming = nil
	if b.ack(z.ID) != 0 {
		t.Fatal("late delivery ack rejected")
	}
}
func TestSMSSIPRejectAndBackpressure(t *testing.T) {
	b := testSMSBridge(t)
	for _, text := range []string{"", "x\x00y", string([]byte{0xff}), strings.Repeat("Ж", 671)} {
		if b.enqueue(smsSIPHash(text), "12345", text) != 1 {
			t.Fatal("invalid text accepted")
		}
	}
	if b.enqueue(smsSIPHash("bad-number"), "sip:123@example.com", "text") != 1 {
		t.Fatal("URI accepted as SMS number")
	}
	for i := 0; i < smsSIPLimit; i++ {
		if b.enqueue(smsSIPHash(string(rune(i))), "12345", "text") != 0 {
			t.Fatal("queue fill")
		}
	}
	if b.enqueue(smsSIPHash("full"), "12345", "text") != 3 {
		t.Fatal("queue not bounded")
	}
	b.enabled = func() bool { return false }
	if b.enqueue(smsSIPHash("disabled"), "12345", "text") != 2 || b.next() != nil || b.processOne() {
		t.Fatal("disabled role processed SMS")
	}
}
func TestSMSSIPFramedIPCAndPersistFailure(t *testing.T) {
	b := testSMSBridge(t)
	a, z := net.Pipe()
	defer a.Close()
	go b.connection(z)
	number, text := "12345", "hello 🌍"
	payload := make([]byte, 36)
	copy(payload, smsSIPHash("ipc"))
	binary.BigEndian.PutUint16(payload[32:], uint16(len(number)))
	binary.BigEndian.PutUint16(payload[34:], uint16(len(text)))
	payload = append(payload, []byte(number+text)...)
	h := []byte("MSM1\x01\x00\x00\x00\x00")
	binary.BigEndian.PutUint32(h[5:], uint32(len(payload)))
	if _, e := a.Write(append(h, payload...)); e != nil {
		t.Fatal(e)
	}
	if _, e := io.ReadFull(a, h); e != nil || h[4] != 0 {
		t.Fatal("IPC enqueue response")
	}
	if len(b.state.Jobs) != 1 || b.state.Jobs[0].Text != text {
		t.Fatal("IPC Unicode")
	}
	b.path = filepath.Join(t.TempDir(), "not-a-directory", "queue.json")
	if e := os.WriteFile(filepath.Dir(b.path), []byte("x"), 0600); e != nil {
		t.Fatal(e)
	}
	if b.enqueue(smsSIPHash("unsaved"), "12345", "text") != 2 || len(b.state.Jobs) != 1 {
		t.Fatal("acknowledged non-durable job")
	}
}

func TestSMSSIPSubmissionResult(t *testing.T) {
	b := testSMSBridge(t)
	id := smsSIPHash("submission")
	if b.submission(id) != 2 {
		t.Fatal("unknown job confirmed")
	}
	if b.enqueue(id, "12345", "text") != 0 || b.submission(id) != 5 {
		t.Fatal("queue confirmed early")
	}
	b.send = func(string, string) error {
		if b.submission(id) != 5 {
			t.Fatal("sending confirmed early")
		}
		return nil
	}
	if !b.processOne() || b.submission(id) != 0 {
		t.Fatal("completed submit unconfirmed")
	}
	if b.next() != nil {
		t.Fatal("successful submission generated an unsolicited message")
	}
	b.state.Jobs[0].State = "uncertain"
	if b.submission(id) != 6 || b.processOne() {
		t.Fatal("uncertain submit replayed or confirmed")
	}
}
