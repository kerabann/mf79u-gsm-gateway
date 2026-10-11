package main

import (
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func TestSMSReceiveCompletionMetadata(t *testing.T) {
	for _, tc := range []struct {
		name     string
		metadata map[string]any
		complete bool
	}{
		{"legacy", map[string]any{}, true},
		{"ordinary", map[string]any{"received_all_concat_sms": "1", "concat_sms_total": "0", "concat_sms_received": "0"}, true},
		{"part1", map[string]any{"received_all_concat_sms": "0", "concat_sms_total": "3", "concat_sms_received": "1"}, false},
		{"part2", map[string]any{"received_all_concat_sms": "0", "concat_sms_total": "3", "concat_sms_received": "2"}, false},
		{"complete", map[string]any{"received_all_concat_sms": "1", "concat_sms_total": "3", "concat_sms_received": "3"}, true},
		{"contradictory flag", map[string]any{"received_all_concat_sms": "1", "concat_sms_total": "3", "concat_sms_received": "2"}, false},
		{"explicit incomplete", map[string]any{"received_all_concat_sms": "0", "concat_sms_total": "3", "concat_sms_received": "3"}, false},
		{"numeric counters", map[string]any{"concat_sms_total": float64(3), "concat_sms_received": float64(3)}, true},
		{"missing part count", map[string]any{"concat_sms_total": "3"}, false},
		{"counter only incomplete", map[string]any{"concat_sms_total": "3", "concat_sms_received": "1"}, false},
		{"negative", map[string]any{"concat_sms_total": "-1"}, false},
		{"overflow", map[string]any{"concat_sms_total": "256"}, false},
		{"malformed", map[string]any{"concat_sms_received": "2;3"}, false},
		{"invalid flag", map[string]any{"received_all_concat_sms": "unknown"}, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			if smsReceiveComplete(tc.metadata) != tc.complete {
				t.Fatal("incorrect readiness")
			}
		})
	}
}

func TestMultipartHeldThroughRestartThenForwardedWholeOnce(t *testing.T) {
	tg, config, inbox := telegramBridgeFixture(t)
	config.DeleteAfterSend = true
	sip := testSMSBridge(t)
	sip.list = tg.list
	sip.refresh()
	if sip.ack(sip.incoming[0].ID) != 0 {
		t.Fatal("fixture baseline ACK")
	}
	tg.tick() // Existing complete inbox is the baseline.
	sent, deleted := 0, 0
	whole := strings.Repeat("long SMS fixture ", 75) // More than 670 characters.
	tg.send = func(_ TelegramSMS, item smsSIPItem) (time.Duration, error) {
		sent++
		if item.Text != whole {
			t.Fatal("fragment forwarded")
		}
		return 0, nil
	}
	tg.retainForSIP = sip.retainIncoming
	tg.delete = func(item smsSIPItem) error {
		deleted++
		if item.Text != whole {
			t.Fatal("incomplete SMS deleted")
		}
		(*inbox)["modem"] = (*inbox)["modem"][:1]
		return nil
	}
	row := telegramInbox("18", "1")
	row["received_all_concat_sms"], row["concat_sms_total"] = "0", "8"
	(*inbox)["modem"] = append((*inbox)["modem"], row)
	for _, received := range []string{"1", "3", "2", "7"} {
		row["concat_sms_received"], row["text"] = received, "partial fixture"
		tg.tick()
		sip.refresh()
		if sent != 0 || deleted != 0 || len(tg.state.Jobs) != 0 || len(tg.state.Seen) != 1 || sip.next() != nil {
			t.Fatal("incomplete SMS entered forwarding/deletion/deduplication")
		}
	}
	// The assembly is stored by the modem. A Control restart must not export it.
	reloaded := &telegramSMSBridge{path: tg.path, config: tg.config, list: tg.list, send: tg.send, delete: tg.delete, retainForSIP: tg.retainForSIP}
	if reloaded.load() != nil {
		t.Fatal("reload")
	}
	reloaded.tick()
	if sent != 0 || deleted != 0 {
		t.Fatal("restart forwarded an incomplete SMS")
	}
	row["received_all_concat_sms"], row["concat_sms_received"], row["text"] = "1", "8", whole
	reloaded.tick()
	sip.refresh() // Telegram already deleted the original; SIP has its whole copy.
	if sent != 1 || deleted != 1 || sip.next() == nil || sip.next().Text != whole {
		t.Fatal("complete SMS was not forwarded once to both destinations")
	}
	if sip.ack(sip.next().ID) != 0 || sip.next() != nil {
		t.Fatal("SIP completion ACK")
	}
	reloaded.tick()
	if sent != 1 || deleted != 1 {
		t.Fatal("complete SMS replayed")
	}
}

func TestIncomingSnapshotDedupeAndWireBound(t *testing.T) {
	row := func(id, text string) map[string]any {
		m := telegramInbox(id, "1")
		m["text"] = text
		m["received_all_concat_sms"] = "1"
		return m
	}
	rows := []any{row("18", "short"), row("18", "complete longer snapshot"), row("18", "complete longer snapshot"), row("19", "different SMS")}
	list := func(storage string) (map[string]any, error) {
		if storage == "sim" {
			return map[string]any{"messages": []any{}}, nil
		}
		return map[string]any{"messages": rows}, nil
	}
	items, e := incomingSMS(list)
	if e != nil || len(items) != 2 || items[0].Text != "complete longer snapshot" {
		t.Fatal("duplicate snapshots forwarded or unrelated messages combined")
	}
	rows = []any{row("18", "same"), row("18", "size")}
	if items, _ := incomingSMS(list); len(items) != 0 {
		t.Fatal("conflicting same-ID content guessed")
	}
	rows = []any{row("18", strings.Repeat("Ж", 1340)), row("19", strings.Repeat("Ж", 1341))}
	if items, _ := incomingSMS(list); len(items) != 1 || len(items[0].Text) != smsIncomingTextLimit {
		t.Fatal("incoming UTF-8 SIP bound or long Unicode support")
	}
}

func TestSMSReceiveDiagnosticsRedactPrivateValues(t *testing.T) {
	row := telegramInbox("private-inbox-id", "1")
	row["number"], row["text"], row["date"] = "private-sender", "private-body", "private-date"
	row["received_all_concat_sms"] = "private-malformed-value"
	row["concat_sms_total"], row["concat_sms_received"] = "3", "1"
	report := smsReceiveMetadata([]any{row})
	data, e := json.Marshal(report)
	if e != nil || strings.Contains(string(data), "private-") || report["pendingRows"] != 1 || report["metadataRows"] != 1 {
		t.Fatal("diagnostic privacy or completion classification")
	}
}
