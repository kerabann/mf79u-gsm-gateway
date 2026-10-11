package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func adminRequest(a *App, method, path, body string, auth, csrf bool) *httptest.ResponseRecorder {
	r := httptest.NewRequest(method, "http://modem"+path, strings.NewReader(body))
	r.Header.Set("Content-Type", "application/json")
	r.Header.Set("Origin", "http://modem")
	if auth {
		r.AddCookie(&http.Cookie{Name: "mf79u_session", Value: "fixture"})
	}
	if csrf {
		r.Header.Set("X-CSRF-Token", "fixture-csrf")
	}
	w := httptest.NewRecorder()
	a.serve(w, r)
	return w
}
func fixtureApp(v *Vendor) *App {
	return &App{settings: defaults(), sessions: map[string]*Session{"fixture": {v: v, csrf: "fixture-csrf", expires: time.Now().Add(time.Minute)}}}
}
func TestCurrentPasswordsRequireAdminAndExplicitCSRF(t *testing.T) {
	a := fixtureApp(nil)
	a.settings.SIP.Password = "trunk-fixture-secret"
	a.settings.SIP.ExtensionPassword = "server-fixture-secret"
	a.settings.WiFi.Password = "wifi-fixture-secret"
	for _, tc := range []struct {
		auth, csrf bool
		code       int
	}{{false, false, 401}, {true, false, 403}, {true, true, 200}} {
		w := adminRequest(a, "GET", "/api/settings/credentials", "", tc.auth, tc.csrf)
		if w.Code != tc.code {
			t.Fatal("credential access control failed")
		}
		if tc.code == 200 {
			var data map[string]string
			json.Unmarshal(w.Body.Bytes(), &data)
			if data["sipPassword"] != a.settings.SIP.Password || data["sipExtensionPassword"] != a.settings.SIP.ExtensionPassword || data["wifiPassword"] != a.settings.WiFi.Password || w.Header().Get("Cache-Control") != "no-store" {
				t.Fatal("credential hydration failed")
			}
		}
	}
	w := adminRequest(a, "GET", "/api/settings", "", true, false)
	if strings.Contains(w.Body.String(), "fixture-secret") {
		t.Fatal("ordinary settings exposed passwords")
	}
}
func TestSMSRESTReadSendDeleteAndGuards(t *testing.T) {
	posts := 0
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		r.ParseForm()
		switch r.Form.Get("cmd") {
		case "loginfo":
			io.WriteString(w, `{"loginfo":"ok"}`)
		case "sms_data_total":
			if r.Form.Get("mem_store") == "1" {
				fmt.Fprintf(w, `{"messages":[{"id":"17","content":%q}]}`, encodeSMS("Привет 🌍"))
			} else {
				io.WriteString(w, `{"messages":[]}`)
			}
		case "sms_capacity_info":
			io.WriteString(w, `{"sms_nv_total":"100","sms_sim_total":"40"}`)
		case "wa_inner_version,cr_version,RD":
			io.WriteString(w, `{"wa_inner_version":"fixture", "cr_version":"fixture", "RD":"fixture"}`)
		case "sms_cmd_status_info":
			io.WriteString(w, `{"sms_cmd_status_result":"3"}`)
		default:
			switch r.Form.Get("goformId") {
			case "SEND_SMS":
				posts++
				if decodeSMS(r.Form.Get("MessageBody")) != "Привет 🌍" || r.Form.Get("encode_type") != "UNICODE" {
					t.Error("Unicode send altered")
				}
				io.WriteString(w, `{"result":"success"}`)
			case "DELETE_SMS":
				posts++
				if r.Form.Get("msg_id") != "17;" && r.Form.Get("msg_id") != "17;18;" {
					t.Error("delete IDs altered")
				}
				io.WriteString(w, `{"result":"success"}`)
			default:
				t.Error("unexpected vendor request")
			}
		}
	}))
	defer backend.Close()
	a := fixtureApp(vendor(backend.URL))
	for _, tc := range []struct {
		method, path, body string
		auth, csrf         bool
		code               int
	}{
		{"GET", "/api/v1/sms/messages", "", false, false, 401},
		{"GET", "/api/v1/sms/messages?storage=invalid", "", true, false, 400},
		{"POST", "/api/v1/sms/messages", `{"number":"123","text":"x"}`, true, false, 403},
		{"POST", "/api/v1/sms/messages", `{"number":"bad","text":"x"}`, true, true, 400},
		{"DELETE", "/api/v1/sms/messages/17;18", "", true, true, 400},
		{"DELETE", "/api/v1/sms/messages", `{"ids":[]}`, true, true, 400},
		{"POST", "/api/v1/sms/messages", `{"number":"123","text":"x"} {}`, true, true, 400},
		{"PATCH", "/api/v1/sms/messages", "{}", true, true, 405},
	} {
		if w := adminRequest(a, tc.method, tc.path, tc.body, tc.auth, tc.csrf); w.Code != tc.code {
			t.Fatalf("guard %s %s = %d", tc.method, tc.path, w.Code)
		}
	}
	if posts != 0 {
		t.Fatal("rejected request reached vendor mutation")
	}
	for _, storage := range []string{"modem", "sim"} {
		w := adminRequest(a, "GET", "/api/v1/sms/messages?storage="+storage, "", true, false)
		if w.Code != 200 || (storage == "modem" && !strings.Contains(w.Body.String(), "Привет 🌍")) {
			t.Fatal("REST storage/Unicode read failed")
		}
	}
	for _, tc := range []struct{ method, path, body string }{
		{"POST", "/api/v1/sms/messages", `{"number":"123456789","text":"Привет 🌍"}`},
		{"DELETE", "/api/v1/sms/messages/17", ""},
		{"DELETE", "/api/v1/sms/messages", `{"ids":["17","18"]}`},
	} {
		if w := adminRequest(a, tc.method, tc.path, tc.body, true, true); w.Code != 200 {
			t.Fatalf("mutation fixture failed: %d %s", w.Code, w.Body.String())
		}
	}
	if posts != 3 {
		t.Fatal("mutations missing")
	}
}
func TestHotspotSecurityReadback(t *testing.T) {
	values := map[string]string{"encmode": "2", "802_1x": "1 0 0 0", "psk_enable": "2 0 0 0", "wpa2_cipher": "8 0 0 0", "passphrase": "116 101 115 116 45 107 101 121 0 99 99"}
	read := func(name string) string { return "wlan0 get_mib:" + values[name] }
	if !hotspotSecurityMatches(read, "test-key") {
		t.Fatal("valid WPA2 or C string padding rejected")
	}
	values["encmode"] = "0"
	if hotspotSecurityMatches(read, "test-key") {
		t.Fatal("open hotspot accepted")
	}
	values["encmode"] = "2"
	if hotspotSecurityMatches(read, "wrong-key") {
		t.Fatal("wrong saved key accepted")
	}
	values["wpa2_cipher"] = "2 0 0 0"
	if hotspotSecurityMatches(read, "test-key") {
		t.Fatal("non-AES cipher accepted")
	}
	values["wpa2_cipher"] = "invalid"
	if hotspotSecurityMatches(read, "test-key") {
		t.Fatal("bad driver response accepted")
	}
}

func TestSMSHeaderAuthentication(t *testing.T) {
	logins := 0
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		r.ParseForm()
		switch r.Form.Get("cmd") {
		case "LD":
			io.WriteString(w, `{"LD":"fixture-challenge"}`)
		case "loginfo":
			io.WriteString(w, `{"loginfo":"ok"}`)
		case "sms_data_total":
			io.WriteString(w, `{"messages":[]}`)
		case "sms_capacity_info":
			io.WriteString(w, `{"sms_nv_total":"100"}`)
		default:
			if r.Form.Get("goformId") != "LOGIN" {
				t.Error("unexpected auth request")
				return
			}
			logins++
			if r.Form.Get("password") == sha(sha("admin-fixture-password")+"fixture-challenge") {
				io.WriteString(w, `{"result":"0"}`)
			} else {
				io.WriteString(w, `{"result":"3"}`)
			}
		}
	}))
	defer backend.Close()
	a := fixtureApp(nil)
	a.base = backend.URL
	for _, tc := range []struct {
		user, password string
		code           int
	}{{"admin", "admin-fixture-password", 200}, {"admin", "wrong-password", 401}, {"other", "admin-fixture-password", 401}} {
		r := httptest.NewRequest("GET", "http://modem/api/v1/sms/messages", nil)
		r.SetBasicAuth(tc.user, tc.password)
		// No cookie, Origin or CSRF; explicit header is the authentication.
		w := httptest.NewRecorder()
		a.serve(w, r)
		if w.Code != tc.code {
			t.Fatalf("Basic authentication = %d", w.Code)
		}
		if strings.Contains(w.Body.String(), tc.password) {
			t.Fatal("password echoed")
		}
	}
	if logins != 2 {
		t.Fatal("wrong username reached vendor")
	}
	// Header authentication must not grant access to the password disclosure API.
	r := httptest.NewRequest("GET", "http://modem/api/settings/credentials", nil)
	r.SetBasicAuth("admin", "admin-fixture-password")
	w := httptest.NewRecorder()
	a.serve(w, r)
	if w.Code != 401 {
		t.Fatal("SMS authentication escaped scope")
	}
}
