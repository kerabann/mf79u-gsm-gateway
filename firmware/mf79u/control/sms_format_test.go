package main

import (
	"encoding/json"
	"testing"
)

func TestRESTNumberPreservesPhonesAndDecodesSender(t *testing.T) {
	for _, s := range []string{"+12345678901", "12345678", "1234", "TEST_DESTINATION_LOCAL", "+00123456", "", "1111222233334444"} {
		if smsNumber(s) != s {
			t.Fatal("plain number altered")
		}
	}
	for _, s := range []string{"+12345678901", "SENDER", "Sender ID", "Όνομα", "12345678"} {
		if smsNumber(encodeSMS(s)) != s {
			t.Fatal("UTF-16BE sender not decoded")
		}
	}
	for _, s := range []string{"00010042", "FFFF", "D800", "not-hex"} {
		if smsNumber(s) != s {
			t.Fatal("invalid sender transformed")
		}
	}
}
func TestRESTDateWithQuarterHourOffsets(t *testing.T) {
	for _, tc := range []struct{ raw, want string }{
		{"26,10,07,18,04,05,+12", "2026-10-07T18:04:05+03:00"},
		{"26,10,07,18,04,05,-14", "2026-10-07T18:04:05-03:30"},
		{"26,1,2,3,4,5,0", "2026-01-02T03:04:05Z"},
		{"26,1,2,3,4,5,4", "2026-01-02T03:04:05+01:00"},
		{"70,1,2,3,4,5,+00", "1970-01-02T03:04:05Z"},
		{"24,2,29,0,0,0,+00", "2024-02-29T00:00:00Z"},
		{"2026-10-07T18:04:05+03:00", "2026-10-07T18:04:05+03:00"},
	} {
		got := smsDate(tc.raw)
		if got == nil || *got != tc.want {
			t.Fatal("date or timezone altered")
		}
	}
	for _, raw := range []string{"", "garbage", "26,2,29,0,0,0,+00", "26,13,1,0,0,0,+00", "26,1,1,24,0,0,+00", "26,1,1,0,60,0,+00", "26,1,1,0,0,0,+57"} {
		if smsDate(raw) != nil {
			t.Fatal("invalid date accepted")
		}
	}
}
func TestRESTDirectionAndRawMetadata(t *testing.T) {
	for tag, want := range map[string]string{"0": "incoming", "1": "incoming", "2": "outgoing", "3": "outgoing", "4": "draft", "8": "unknown", "": "unknown"} {
		if smsDirection(tag) != want {
			t.Fatal("wrong direction")
		}
	}
	rawNumber := encodeSMS("SENDER")
	value := map[string]any{"messages": []any{map[string]any{"id": "17", "number": rawNumber, "date": "26,10,07,18,04,05,+12", "tag": "0", "text": "Привет"}, map[string]any{"id": "18", "date": "unknown", "tag": "4"}}}
	normalized := normalizeSMSREST(value)
	bytes, e := json.Marshal(normalized)
	if e != nil {
		t.Fatal(e)
	}
	var result map[string]any
	json.Unmarshal(bytes, &result)
	msgs := result["messages"].([]any)
	m := msgs[0].(map[string]any)
	if m["number"] != "SENDER" || m["date"] != "2026-10-07T18:04:05+03:00" || m["direction"] != "incoming" || m["rawNumber"] != rawNumber || m["rawDate"] != "26,10,07,18,04,05,+12" || m["tag"] != "0" || m["text"] != "Привет" {
		t.Fatal("REST message normalization lost metadata")
	}
	if msgs[1].(map[string]any)["date"] != nil {
		t.Fatal("unknown date must be JSON null")
	}
}
