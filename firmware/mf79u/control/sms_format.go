package main

import (
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"
)

var smsSenderHex = regexp.MustCompile(`^(?:[0-9a-fA-F]{4})+$`)
var smsSenderDigits = regexp.MustCompile(`^[0-9]+$`)
var smsVendorDate = regexp.MustCompile(`^(\d{2}),(\d{1,2}),(\d{1,2}),(\d{1,2}),(\d{1,2}),(\d{1,2}),([+-]?)(\d{1,2})$`)

func smsNumber(value string) string {
	raw := strings.TrimSpace(value)
	// Preserve plain phone numbers, including local numbers and short codes.
	// B03 encodes ASCII numbers/sender IDs as UTF-16BE hex code units.
	if !smsSenderHex.MatchString(raw) || smsSenderDigits.MatchString(raw) && !strings.HasPrefix(raw, "00") {
		return raw
	}
	decoded := decodeSMS(raw)
	for _, r := range decoded {
		if r == unicode.ReplacementChar || r == 0xffff || unicode.IsControl(r) {
			return raw
		}
	}
	return strings.TrimSpace(decoded)
}
func smsDate(value string) *string {
	raw := strings.TrimSpace(value)
	if t, e := time.Parse(time.RFC3339, raw); e == nil {
		s := t.Format(time.RFC3339)
		return &s
	}
	m := smsVendorDate.FindStringSubmatch(raw)
	if m == nil {
		return nil
	}
	n := make([]int, 7)
	for i, index := range []int{1, 2, 3, 4, 5, 6, 8} {
		n[i], _ = strconv.Atoi(m[index])
	}
	year := n[0] + 2000
	if n[0] >= 70 {
		year = n[0] + 1900
	}
	if n[1] < 1 || n[1] > 12 || n[2] < 1 || n[2] > 31 || n[3] > 23 || n[4] > 59 || n[5] > 59 || n[6] > 56 {
		return nil
	}
	offset := n[6] * 15 * 60
	if m[7] == "-" {
		offset = -offset
	}
	t := time.Date(year, time.Month(n[1]), n[2], n[3], n[4], n[5], 0, time.FixedZone("", offset))
	if t.Year() != year || int(t.Month()) != n[1] || t.Day() != n[2] {
		return nil
	}
	formatted := t.Format(time.RFC3339)
	return &formatted
}
func smsDirection(tag string) string {
	// B03 smslist.js renders 0/1 with smsOtherTmpl (received), 2/3 with
	// smsMeTmpl (outgoing), and 4 as a draft. Preserve unknown future tags.
	switch tag {
	case "0", "1":
		return "incoming"
	case "2", "3":
		return "outgoing"
	case "4":
		return "draft"
	default:
		return "unknown"
	}
}
func normalizeSMSREST(value map[string]any) map[string]any {
	for _, item := range value["messages"].([]any) {
		m, ok := item.(map[string]any)
		if !ok {
			continue
		}
		number, date := str(m["number"]), str(m["date"])
		m["rawNumber"], m["rawDate"] = number, date
		m["number"], m["date"] = smsNumber(number), smsDate(date)
		m["direction"] = smsDirection(str(m["tag"]))
	}
	return value
}
