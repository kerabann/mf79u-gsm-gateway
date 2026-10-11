package main

import "strconv"

// Matches the existing SIP incoming body bound, including UTF-8 text. The
// outgoing SMS limit remains 670 characters; incoming concatenation is distinct.
const smsIncomingTextLimit = 2680

// B03 assembles segments in its own inbox. An incomplete row's content grows
// under the same ID; never enqueue it or delete it while parts are outstanding.
// Firmware without these optional fields retains the ordinary legacy behavior.
func smsReceiveComplete(m map[string]any) bool {
	flag := str(m["received_all_concat_sms"])
	if flag != "" && flag != "1" {
		return false
	}
	counts := [2]int{}
	present := [2]bool{}
	for i, key := range []string{"concat_sms_total", "concat_sms_received"} {
		value := str(m[key])
		if value == "" {
			continue
		}
		count, e := strconv.Atoi(value)
		if e != nil || count < 0 || count > 255 {
			return false
		}
		counts[i], present[i] = count, true
	}
	if present[0] && present[1] && counts[0] != counts[1] {
		return false
	}
	if flag == "1" {
		return true
	}
	if counts[0] > 0 {
		return present[1] && counts[0] == counts[1]
	}
	return counts[1] == 0
}
