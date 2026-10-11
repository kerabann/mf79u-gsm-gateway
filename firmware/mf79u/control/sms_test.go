package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestEmbeddedUIRequiresRevalidation(t *testing.T) {
	a := &App{}
	r := httptest.NewRequest("GET", "http://modem/app.js", nil)
	w := httptest.NewRecorder()
	a.serve(w, r)
	if w.Code != http.StatusOK {
		t.Fatalf("app.js returned %d", w.Code)
	}
	if got := w.Header().Get("Cache-Control"); got != "no-cache" {
		t.Fatalf("app.js cache policy = %q", got)
	}
	if w.Header().Get("ETag") == "" {
		t.Fatal("Missing content-based asset version")
	}
}

func TestB03SMSStorageAndExpiredSession(t *testing.T) {
	loggedIn, queries := true, 0
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		r.ParseForm()
		switch r.Form.Get("cmd") {
		case "loginfo":
			state := ""
			if loggedIn {
				state = "ok"
			}
			fmt.Fprintf(w, `{"loginfo":%q}`, state)
		case "sms_data_total":
			queries++
			if r.Form.Get("mem_store") == "1" {
				fmt.Fprintf(w, `{"messages":[{"id":"17","content":%q}]}`, encodeSMS("Привет 🌍"))
			} else if r.Form.Get("mem_store") == "0" {
				io.WriteString(w, `{"messages":[]}`)
			} else {
				t.Error("incorrect B03 storage selector")
			}
		case "sms_capacity_info":
			if r.Form.Get("multi_data") != "" {
				t.Error("SMS capacity was sent through the NV multi_data handler")
			}
			io.WriteString(w, `{"sms_nv_total":"100","sms_nvused_total":"1","sms_sim_total":"40"}`)
		default:
			t.Errorf("unexpected query: %s", r.Form.Get("cmd"))
		}
	}))
	defer backend.Close()
	v := vendor(backend.URL)
	modem, e := v.sms("modem", "")
	if e != nil {
		t.Fatal(e)
	}
	messages := modem["messages"].([]any)
	if len(messages) != 1 || messages[0].(map[string]any)["text"] != "Привет 🌍" {
		t.Fatal("modem storage or Unicode decoding failed")
	}
	sim, e := v.sms("sim", "")
	if e != nil || len(sim["messages"].([]any)) != 0 {
		t.Fatal("empty SIM storage was not returned as an empty list")
	}
	if _, e := v.sms("invalid", ""); e == nil {
		t.Fatal("unknown storage accepted")
	}
	loggedIn = false
	if _, e := v.sms("modem", ""); !errors.Is(e, errVendorSession) {
		t.Fatal("expired vendor session was not identified")
	}
	if queries != 2 {
		t.Fatal("invalid storage or expired session queried SMS data")
	}
}

func TestUITabsShareB03Session(t *testing.T) {
	latest, loginCount := "", 0
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		r.ParseForm()
		if strings.Contains(r.Form.Get("cmd"), "loginfo") {
			cookie, _ := r.Cookie("stok")
			if cookie != nil && cookie.Value == latest {
				io.WriteString(w, `{"loginfo":"ok"}`)
			} else {
				io.WriteString(w, `{"loginfo":""}`)
			}
			return
		}
		if r.Form.Get("goformId") == "LOGIN" {
			loginCount++
			latest = fmt.Sprint(loginCount)
			http.SetCookie(w, &http.Cookie{Name: "stok", Value: latest, Path: "/", HttpOnly: true})
			io.WriteString(w, `{"result":"0"}`)
			return
		}
		switch r.Form.Get("cmd") {
		case "LD":
			io.WriteString(w, `{"LD":"test-challenge"}`)
		case "sms_data_total":
			io.WriteString(w, `{"messages":[]}`)
		case "sms_capacity_info":
			io.WriteString(w, `{"sms_nv_total":"100"}`)
		}
	}))
	defer backend.Close()
	a := &App{base: backend.URL, sessions: map[string]*Session{}}
	var tabs []*http.Cookie
	for i := 0; i < 2; i++ {
		r := httptest.NewRequest("POST", "http://modem/api/login", strings.NewReader(`{"password":"test-password"}`))
		r.Header.Set("Origin", "http://modem")
		r.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		a.serve(w, r)
		if w.Code != 200 {
			t.Fatal("UI login failed")
		}
		tabs = append(tabs, w.Result().Cookies()[0])
	}
	for _, tab := range tabs {
		r := httptest.NewRequest("GET", "http://modem/api/sms?storage=sim", nil)
		r.AddCookie(tab)
		w := httptest.NewRecorder()
		a.serve(w, r)
		var data map[string]any
		json.Unmarshal(w.Body.Bytes(), &data)
		if w.Code != 200 || data["storage"] != "sim" {
			t.Fatal("a second UI login invalidated the first tab")
		}
	}
	latest = "external-login"
	r := httptest.NewRequest("GET", "http://modem/api/status", nil)
	r.AddCookie(tabs[0])
	w := httptest.NewRecorder()
	a.serve(w, r)
	var status map[string]any
	json.Unmarshal(w.Body.Bytes(), &status)
	if w.Code != 200 || status["vendorSession"] != true || loginCount != 3 || a.sessions[tabs[0].Value] == nil {
		t.Fatalf("expired vendor session was not renewed: code=%d body=%s logins=%d session=%v", w.Code, w.Body.String(), loginCount, a.sessions[tabs[0].Value] != nil)
	}
	r = httptest.NewRequest("GET", "http://modem/api/sms", nil)
	r.AddCookie(tabs[0])
	w = httptest.NewRecorder()
	a.serve(w, r)
	if w.Code != http.StatusOK || a.sessions[tabs[0].Value] == nil {
		t.Fatal("SMS did not reuse the automatically renewed vendor session")
	}
}
