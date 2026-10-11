package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestSystemInfoIMEIReadAndFailure(t *testing.T) {
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			t.Error("System info must not mutate the vendor configuration")
		}
		io.WriteString(w, `{"loginfo":"ok","device_name":"fixture"}`)
	}))
	defer backend.Close()
	for _, tc := range []struct {
		name, script string
		available    bool
	}{
		{"missing", "", false},
		{"invalid", "#!/bin/sh\necho unavailable\n", false},
		{"failed", "#!/bin/sh\nexit 3\n", false},
		{"read", "#!/bin/sh\n[ \"$1\" = read ] || exit 2\nprintf '%s\\n' '490154203237518'\n", true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			a := fixtureApp(vendor(backend.URL))
			a.native, a.dir = true, t.TempDir()
			if tc.script != "" {
				if e := os.Mkdir(filepath.Join(a.dir, "tools"), 0700); e != nil {
					t.Fatal(e)
				}
				if e := os.WriteFile(filepath.Join(a.dir, "tools/system-imei"), []byte(tc.script), 0700); e != nil {
					t.Fatal(e)
				}
			}
			if w := adminRequest(a, "GET", "/api/system/info", "", false, false); w.Code != 401 {
				t.Fatal("System identity requires an authenticated administrator")
			}
			w := adminRequest(a, "GET", "/api/system/info", "", true, false)
			var info map[string]any
			if w.Code != 200 || json.Unmarshal(w.Body.Bytes(), &info) != nil || info["model"] != "ZTE MF79U" {
				t.Fatal("IMEI failure must not hide the remaining device information")
			}
			if tc.available {
				if info["imei"] != "490154203237518" || info["imeiError"] != nil {
					t.Fatal("Current IMEI was not returned after a successful read")
				}
			} else if info["imei"] != nil || info["imeiError"] != "IMEI read unavailable" {
				t.Fatal("Unavailable IMEI must return an explicit generic error")
			}
		})
	}
}

func TestSystemValidationAndLogPrivacy(t *testing.T) {
	if !validIMEI("490154203237518") || validIMEI("490154203237519") || validIMEI("49015420323751;") {
		t.Fatal("IMEI checksum validation")
	}
	if validSystemPassword("short", 12, 128) || validSystemPassword("line\nbreak123", 8, 32) || !validSystemPassword("A valid password!", 12, 128) {
		t.Fatal("password validation")
	}
	text := sanitizeLog("IMS registered\nAuthorization: secret\nFrom: <sip:+123456789@pbx>\nIMSI 999999999999999\nSMS_TEXT=private\ncodec=G722")
	for _, secret := range []string{"secret", "123456789", "999999999999999", "private\n"} {
		if strings.Contains(text, secret) {
			t.Fatal("private log data leaked")
		}
	}
	if !strings.Contains(text, "IMS registered") || !strings.Contains(text, "codec=G722") {
		t.Fatal("operational events lost")
	}
}
func TestSystemRequiresAdminAndCSRF(t *testing.T) {
	a := fixtureApp(nil)
	a.dir = t.TempDir()
	for _, path := range []string{"password", "imei", "reboot", "ssh"} {
		method := "POST"
		if path == "ssh" {
			method = "PUT"
		}
		for _, tc := range []struct {
			auth, csrf bool
			code       int
		}{{false, false, 401}, {true, false, 403}, {true, true, 409}} {
			w := adminRequest(a, method, "/api/system/"+path, "{}", tc.auth, tc.csrf)
			if w.Code != tc.code {
				t.Fatalf("%s status %d", path, w.Code)
			}
		}
	}
	w := adminRequest(a, "GET", "/api/system/logs?source=../../etc/shadow", "", true, false)
	if w.Code != 400 {
		t.Fatal("log path allowlist bypass")
	}
}
func TestPasswordChangeB03HashContract(t *testing.T) {
	old, new := sha("fixture-old-password"), sha("fixture-new-password")
	key := old
	posts := 0
	logins := 0
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		r.ParseForm()
		switch r.Form.Get("cmd") {
		case "LD":
			io.WriteString(w, `{"LD":"fixture-challenge"}`)
		case "wa_inner_version,cr_version,RD":
			io.WriteString(w, `{"wa_inner_version":"B03","cr_version":"fixture","RD":"fixture"}`)
		default:
			switch r.Form.Get("goformId") {
			case "LOGIN":
				logins++
				if r.Form.Get("password") != sha(key+"fixture-challenge") {
					io.WriteString(w, `{"result":"3"}`)
				} else {
					io.WriteString(w, `{"result":"0"}`)
				}
			case "CHANGE_PASSWORD":
				posts++
				if r.Form.Get("oldPassword") != old || r.Form.Get("newPassword") != new {
					t.Error("plaintext or incorrect hash used")
				}
				key = new
				fmt.Fprint(w, `{"result":"success"}`)
			default:
				t.Error("unexpected vendor request")
			}
		}
	}))
	defer backend.Close()
	v := vendor(backend.URL)
	if changed, e := v.changePassword(old, new); !changed || e != nil {
		t.Fatal(e)
	}
	if posts != 1 || logins != 2 {
		t.Fatal("change or re-auth was retried incorrectly")
	}
	if changed, e := v.changePassword(old, new); changed || e == nil || posts != 1 {
		t.Fatal("invalid current password allowed")
	}
}

func TestAdminPasswordRotationInvalidatesEverySession(t *testing.T) {
	old, newKey := sha("fixture-old-password"), sha("fixture-new-password")
	key := old
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		r.ParseForm()
		switch r.Form.Get("cmd") {
		case "LD":
			io.WriteString(w, `{"LD":"fixture"}`)
		case "wa_inner_version,cr_version,RD":
			io.WriteString(w, `{"wa_inner_version":"B03","cr_version":"fixture","RD":"fixture"}`)
		default:
			switch r.Form.Get("goformId") {
			case "LOGIN":
				if r.Form.Get("password") == sha(key+"fixture") {
					io.WriteString(w, `{"result":"0"}`)
				} else {
					io.WriteString(w, `{"result":"3"}`)
				}
			case "CHANGE_PASSWORD":
				key = newKey
				io.WriteString(w, `{"result":"success"}`)
			}
		}
	}))
	defer backend.Close()
	a := fixtureApp(vendor(backend.URL))
	a.native = true
	a.sessions["fixture"].vendorKey = old
	a.sessions["other"] = a.sessions["fixture"]
	w := adminRequest(a, "POST", "/api/system/password", `{"currentPassword":"fixture-old-password","newPassword":"fixture-new-password","confirmPassword":"fixture-new-password"}`, true, true)
	if w.Code != 200 || len(a.sessions) != 0 || !strings.Contains(w.Header().Get("Set-Cookie"), "Max-Age=0") {
		t.Fatal("Password rotation left an admin session active")
	}
}

func TestManagementCookieTracksIdleTimeout(t *testing.T) {
	a := fixtureApp(nil)
	before := time.Now()
	w := adminRequest(a, "GET", "/api/session", "", true, false)
	cookies := w.Result().Cookies()
	if w.Code != 200 || len(cookies) != 1 || cookies[0].Name != "mf79u_session" || cookies[0].Value != "fixture" || cookies[0].MaxAge != 1800 || !cookies[0].HttpOnly || cookies[0].SameSite != http.SameSiteStrictMode || a.sessions["fixture"].expires.Before(before.Add(29*time.Minute)) {
		t.Fatal("Browser cookie and management idle timeout were not renewed together")
	}
	a.sessions["fixture"].expires = time.Now().Add(-time.Second)
	w = adminRequest(a, "GET", "/api/session", "", true, false)
	if w.Code != 401 || len(w.Result().Cookies()) != 0 || len(a.sessions) != 0 {
		t.Fatal("Expired management session was renewed")
	}
}
