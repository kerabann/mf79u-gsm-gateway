package main

import (
	"sort"
	"strconv"
)

// Aggregate only the documented concat fields. Never return an inbox ID,
// sender, body, date, cookie or a raw malformed metadata value.
func smsReceiveMetadata(rows []any) map[string]any {
	complete, pending, metadata, duplicates := 0, 0, 0, 0
	ids := make(map[string]bool)
	patterns := make(map[string]int)
	for _, raw := range rows {
		m, ok := raw.(map[string]any)
		if !ok || smsDirection(str(m["tag"])) != "incoming" {
			continue
		}
		id := str(m["id"])
		if ids[id] {
			duplicates++
		}
		ids[id] = true
		flag := str(m["received_all_concat_sms"])
		if flag == "" {
			flag = "missing"
		} else if flag != "0" && flag != "1" {
			flag = "invalid"
		}
		values := [2]string{"missing", "missing"}
		for i, key := range []string{"concat_sms_total", "concat_sms_received"} {
			if value := str(m[key]); value != "" {
				values[i] = "invalid"
				if count, e := strconv.Atoi(value); e == nil && count >= 0 && count <= 255 {
					values[i] = strconv.Itoa(count)
				}
			}
		}
		if flag != "missing" || values[0] != "missing" || values[1] != "missing" {
			metadata++
		}
		if smsReceiveComplete(m) {
			complete++
		} else {
			pending++
		}
		patterns["all="+flag+",total="+values[0]+",received="+values[1]]++
	}
	keys := make([]string, 0, len(patterns))
	for key := range patterns {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	groups := []map[string]any{}
	for _, key := range keys {
		groups = append(groups, map[string]any{"metadata": key, "rows": patterns[key]})
	}
	return map[string]any{"incomingRows": complete + pending, "completeRows": complete, "pendingRows": pending,
		"metadataRows": metadata, "duplicateRows": duplicates, "patterns": groups}
}

func smsReceiveDiagnostics(base string) map[string]any {
	report := map[string]any{"readOnly": true, "smsSubmitted": false, "messagesDeleted": false}
	key, e := smsSIPKey()
	if e != nil {
		report["error"] = "local_auth_unavailable"
		return report
	}
	v := vendor(base)
	for _, storage := range []string{"modem", "sim"} {
		value, e := v.sms(storage, key)
		if e != nil {
			report["error"] = "inbox_unavailable"
			return report
		}
		report[storage] = smsReceiveMetadata(value["messages"].([]any))
	}
	return report
}
