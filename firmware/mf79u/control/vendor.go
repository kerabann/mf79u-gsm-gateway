package main

import (
	"crypto/md5"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"strings"
	"sync"
	"time"
	"unicode/utf16"
)

type Vendor struct {
	base   string
	client *http.Client
	mu     sync.Mutex
}

var errVendorSession = errors.New("The ZTE backend session expired and automatic sign-in failed. Sign out and sign in again.")

// An unauthenticated B03 request returns an empty NV field, not HTTP 401.
// Check loginfo rather than treating that response as an empty SMS inbox.
func (v *Vendor) authenticated() error {
	r, e := v.get("loginfo")
	if e != nil {
		return e
	}
	if str(r["loginfo"]) != "ok" {
		return errVendorSession
	}
	return nil
}

func vendor(base string) *Vendor {
	jar, _ := cookiejar.New(nil)
	return &Vendor{base: base, client: &http.Client{Jar: jar, Timeout: 12 * time.Second, Transport: &http.Transport{Proxy: nil, MaxIdleConns: 2, MaxIdleConnsPerHost: 2, IdleConnTimeout: 30 * time.Second}}}
}
func (v *Vendor) request(fields url.Values, post bool) (map[string]any, error) {
	fields.Set("isTest", "false")
	endpoint := "/goform/goform_get_cmd_process"
	method := "GET"
	var body io.Reader
	if post {
		endpoint = "/goform/goform_set_cmd_process"
		method = "POST"
		body = strings.NewReader(fields.Encode())
	} else {
		endpoint += "?" + fields.Encode()
	}
	req, e := http.NewRequest(method, v.base+endpoint, body)
	if e != nil {
		return nil, e
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Referer", v.base+"/index.html")
	req.Header.Set("Origin", v.base)
	req.Header.Set("X-Requested-With", "XMLHttpRequest")
	r, e := v.client.Do(req)
	if e != nil {
		return nil, errors.New("The modem backend is not responding")
	}
	defer r.Body.Close()
	if r.StatusCode != 200 {
		return nil, fmt.Errorf("Modem backend: HTTP %d", r.StatusCode)
	}
	var result map[string]any
	e = json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&result)
	if e != nil {
		return nil, errors.New("Invalid response from the modem backend")
	}
	return result, nil
}
func values(k, v string) url.Values { return url.Values{k: []string{v}} }
func str(v any) string {
	if v == nil {
		return ""
	}
	return fmt.Sprint(v)
}
func (v *Vendor) get(cmd string) (map[string]any, error) {
	return v.request(url.Values{"cmd": {cmd}, "multi_data": {"1"}}, false)
}
func sha(s string) string {
	h := sha256.Sum256([]byte(s))
	return strings.ToUpper(hex.EncodeToString(h[:]))
}
func md(s string) string { h := md5.Sum([]byte(s)); return hex.EncodeToString(h[:]) }
func (v *Vendor) login(password string) error {
	_, e := v.loginWithKey(password)
	return e
}
func (v *Vendor) loginWithKey(password string) (string, error) {
	key := sha(password)
	v.mu.Lock()
	defer v.mu.Unlock()
	if e := v.loginKeyLocked(key); e != nil {
		return "", e
	}
	return key, nil
}
func (v *Vendor) loginKeyLocked(key string) error {
	if len(key) != 64 {
		return errors.New("ZTE sign-in key unavailable")
	}
	r, e := v.get("LD")
	if e != nil {
		return e
	}
	ld := str(r["LD"])
	if ld == "" {
		return errors.New("Login challenge unavailable")
	}
	r, e = v.request(url.Values{"goformId": {"LOGIN"}, "password": {sha(key + ld)}}, true)
	if e != nil {
		return e
	}
	if str(r["result"]) != "0" && str(r["result"]) != "4" {
		return errors.New("Incorrect password or sign-in temporarily blocked")
	}
	return nil
}
func (v *Vendor) ensureAuthenticatedLocked(key string) error {
	e := v.authenticated()
	if e == nil || !errors.Is(e, errVendorSession) {
		return e
	}
	if e := v.loginKeyLocked(key); e != nil {
		return errVendorSession
	}
	return v.authenticated()
}
func (v *Vendor) status(key, cmd string) (map[string]any, error) {
	v.mu.Lock()
	defer v.mu.Unlock()
	r, e := v.get(cmd)
	if e != nil {
		return nil, e
	}
	if str(r["loginfo"]) == "ok" {
		return r, nil
	}
	if e := v.loginKeyLocked(key); e != nil {
		return nil, errVendorSession
	}
	r, e = v.get(cmd)
	if e != nil {
		return nil, e
	}
	if str(r["loginfo"]) != "ok" {
		return nil, errVendorSession
	}
	return r, nil
}
func (v *Vendor) getAuthenticated(key, cmd string) (map[string]any, error) {
	v.mu.Lock()
	defer v.mu.Unlock()
	if e := v.ensureAuthenticatedLocked(key); e != nil {
		return nil, e
	}
	return v.get(cmd)
}
func (v *Vendor) postAuthenticated(key string, fields url.Values) (map[string]any, error) {
	v.mu.Lock()
	defer v.mu.Unlock()
	if e := v.ensureAuthenticatedLocked(key); e != nil {
		return nil, e
	}
	return v.post(fields)
}
func (v *Vendor) post(fields url.Values) (map[string]any, error) {
	// ZTE's own B03 service.js uses MD5(MD5(wa_inner_version + cr_version) + RD).
	// Never log either authentication data or complete vendor responses.
	version, e := v.get("wa_inner_version,cr_version,RD")
	if e != nil {
		return nil, e
	}
	rd := str(version["RD"])
	if rd != "" {
		fields.Set("AD", md(md(str(version["wa_inner_version"])+str(version["cr_version"]))+rd))
	}
	r, e := v.request(fields, true)
	if e != nil {
		return nil, e
	}
	if str(r["result"]) != "success" && str(r["result"]) != "0" {
		return nil, errors.New("The modem rejected the operation")
	}
	return r, nil
}
func decodeSMS(s string) string {
	if len(s) == 0 || len(s)%4 != 0 {
		return s
	}
	b, e := hex.DecodeString(s)
	if e != nil {
		return s
	}
	u := make([]uint16, len(b)/2)
	for i := range u {
		u[i] = uint16(b[i*2])<<8 | uint16(b[i*2+1])
	}
	return string(utf16.Decode(u))
}
func encodeSMS(s string) string {
	var out strings.Builder
	for _, u := range utf16.Encode([]rune(s)) {
		fmt.Fprintf(&out, "%04X", u)
	}
	return out.String()
}
func (v *Vendor) sms(storage, key string) (map[string]any, error) {
	v.mu.Lock()
	defer v.mu.Unlock()
	store := "1" // B03: modem/NV=1, SIM=0.
	if storage == "sim" {
		store = "0"
	} else if storage != "modem" {
		return nil, errors.New("SMS storage must be modem or sim")
	}
	if e := v.ensureAuthenticatedLocked(key); e != nil {
		return nil, e
	}
	messages := []any{}
	for page := 0; page < 100; page++ {
		r, e := v.request(url.Values{"cmd": {"sms_data_total"}, "page": {fmt.Sprint(page)}, "data_per_page": {"100"}, "mem_store": {store}, "tags": {"10"}, "order_by": {"order by id desc"}}, false)
		if e != nil {
			return nil, e
		}
		batch, ok := r["messages"].([]any)
		if !ok {
			if e := v.authenticated(); e != nil {
				return nil, e
			}
			return nil, errors.New("The SMS API did not return a message list")
		}
		for _, m := range batch {
			if x, ok := m.(map[string]any); ok {
				x["text"] = decodeSMS(str(x["content"]))
				delete(x, "content")
			}
			messages = append(messages, m)
		}
		if len(batch) < 100 {
			break
		}
		if page == 99 {
			return nil, errors.New("SMS page limit exceeded")
		}
	}
	// This is a special SMS handler, not an NV multi_data query.
	capacity, e := v.request(values("cmd", "sms_capacity_info"), false)
	if e != nil {
		return nil, e
	}
	for k, val := range capacity {
		if strings.HasPrefix(k, "sms_") && strings.HasPrefix(str(val), "-") {
			return nil, errors.New("The SMS service returned invalid capacity counters")
		}
	}
	return map[string]any{"messages": messages, "capacity": capacity, "storage": storage}, nil
}
func (v *Vendor) smsAction(action string, ids []string, number, text, key string) error {
	v.mu.Lock()
	defer v.mu.Unlock()
	if e := v.ensureAuthenticatedLocked(key); e != nil {
		return e
	}
	fields := url.Values{}
	switch action {
	case "delete", "read":
		if len(ids) < 1 || len(ids) > 100 {
			return errors.New("Select messages")
		}
		for _, id := range ids {
			if !regexpID.MatchString(id) {
				return errors.New("Invalid SMS ID")
			}
		}
		fields.Set("msg_id", strings.Join(ids, ";")+";")
		if action == "delete" {
			fields.Set("goformId", "DELETE_SMS")
		} else {
			fields.Set("goformId", "SET_MSG_READ")
			fields.Set("tag", "0")
		}
	case "send":
		if !numberRE.MatchString(number) || len([]rune(text)) < 1 || len([]rune(text)) > 670 {
			return errors.New("Invalid phone number or SMS text (1–670 characters)")
		}
		fields = url.Values{"goformId": {"SEND_SMS"}, "Number": {number}, "MessageBody": {encodeSMS(text)}, "encode_type": {"UNICODE"}, "sms_time": {time.Now().Format("06;01;02;15;04;05;+00")}, "ID": {"-1"}}
	default:
		return errors.New("Unknown SMS operation")
	}
	if _, e := v.post(fields); e != nil {
		return e
	}
	if action == "read" {
		return nil
	}
	command := "4" // SEND_SMS; B03 reports per-command status, not a global field.
	if action == "delete" {
		command = "6"
	}
	for i := 0; i < 40; i++ {
		time.Sleep(250 * time.Millisecond)
		r, e := v.request(url.Values{"cmd": {"sms_cmd_status_info"}, "sms_cmd": {command}}, false)
		if e != nil {
			return e
		}
		switch str(r["sms_cmd_status_result"]) {
		case "3":
			return nil
		case "2":
			return errors.New("The SMS operation failed")
		}
	}
	return errors.New("The SMS API did not confirm completion. Refresh the list before trying again.")
}
