package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDisabledVoiceAndHotspotMigration(t *testing.T) {
	s := defaults()
	s.SIP.Role = "DISABLED"
	s.SIP.Server, s.SIP.Username, s.SIP.IncomingUser = "", "", ""
	s.SIP.TrustedPeers, s.SIP.Codecs = nil, nil
	if e := validate(s); e != nil {
		t.Fatal(e)
	}
	if !strings.HasPrefix(string(gatewayINI(s, t.TempDir())), "role=DISABLED\n") {
		t.Fatal("disabled mode not persisted")
	}
	s.SIP.Role = "TRUNK"
	if validate(s) == nil {
		t.Fatal("empty active trunk accepted")
	}
	dir := t.TempDir()
	s = defaults()
	s.WiFi.Enabled, s.WiFi.SSID, s.WiFi.Password = true, "private-uplink", "station-secret"
	b, _ := json.Marshal(s)
	if e := os.WriteFile(filepath.Join(dir, "settings.json"), b, 0600); e != nil {
		t.Fatal(e)
	}
	migrated, e := readSettings(dir)
	if e != nil {
		t.Fatal(e)
	}
	if migrated.WiFi.Mode != "HOTSPOT" || migrated.WiFi.Password != "" || migrated.WiFi.SSID != "" {
		t.Fatal("station credentials reused as hotspot profile")
	}
	migrated.WiFi.Enabled, migrated.WiFi.SSID, migrated.WiFi.Password = true, "Test hotspot", "protected-test-password"
	migrated.WiFi.Hidden = true
	if e := validate(migrated); e != nil {
		t.Fatal(e)
	}
	migrated.WiFi.Security = "OPEN"
	if validate(migrated) == nil {
		t.Fatal("open hotspot accepted")
	}
}

func TestSecretsAndValidation(t *testing.T) {
	s := defaults()
	s.SIP.Password = "test-secret"
	s.SIP.ExtensionPassword = "local-test-secret"
	s.WiFi.Password = "test-wifi-secret"
	b, _ := json.Marshal(publicSettings(s))
	if strings.Contains(string(b), "test-secret") || strings.Contains(string(b), "local-test-secret") || strings.Contains(string(b), "test-wifi-secret") {
		t.Fatal("secret exposed")
	}
	if e := atomicFile(filepath.Join(t.TempDir(), "settings.json"), []byte("{}"), 0600); e != nil {
		t.Fatal(e)
	}
	s.SIP.Codecs = []string{"OPUS", "G722", "PCMA", "PCMU", "G729"}
	if e := validate(s); e != nil {
		t.Fatal(e)
	}
	s = defaults()
	s.SIP.Role = "SERVER"
	s.SIP.ExtensionPassword = "twelve-chars-or-more"
	s.SIP.Transport = "UDP"
	s.SIP.Bind = "192.168.0.1"
	if e := validate(s); e != nil {
		t.Fatal(e)
	}
	if !strings.Contains(string(gatewayINI(s, t.TempDir())), "role=SERVER\nextension=100\n") {
		t.Fatal("local registrar settings missing")
	}
	s.SIP.Transport = "TCP"
	if validate(s) == nil {
		t.Fatal("unsupported local registrar transport accepted")
	}
	s.SIP.Server = "pbx.example.com\r\nInjected: bad"
	if validate(s) == nil {
		t.Fatal("SIP injection accepted")
	}
	s = defaults()
	s.SIP.Codecs = []string{"G722", "G722"}
	if validate(s) == nil {
		t.Fatal("duplicate codec accepted")
	}
	s = defaults()
	s.WiFi.Network = Network{Mode: "STATIC", Address: "192.168.1.4/24", Gateway: "192.168.1.1", DNS: []string{"1.1.1.1"}}
	if e := validate(s); e != nil {
		t.Fatal(e)
	}
	s.WiFi.Network.Address = "shell;injection"
	if validate(s) == nil {
		t.Fatal("bad address accepted")
	}
}
func TestVendorAuthenticationAndSMS(t *testing.T) {
	fake := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		r.ParseForm()
		if r.Method == "GET" {
			io.WriteString(w, `{"LD":"challenge","RD":"rd","wa_inner_version":"a","cr_version":"b"}`)
			return
		}
		if r.Form.Get("goformId") == "LOGIN" {
			if r.Form.Get("password") != sha(sha("test-password")+"challenge") {
				t.Error("incorrect SHA256 login")
			}
			io.WriteString(w, `{"result":"0"}`)
			return
		}
		if r.Form.Get("AD") != md(md("ab")+"rd") {
			t.Error("incorrect AD challenge")
		}
		io.WriteString(w, `{"result":"success"}`)
	}))
	defer fake.Close()
	v := vendor(fake.URL)
	if e := v.login("test-password"); e != nil {
		t.Fatal(e)
	}
	if _, e := v.post(url.Values{"goformId": {"SET_MSG_READ"}}); e != nil {
		t.Fatal(e)
	}
	text := "Привет 🌍"
	if decodeSMS(encodeSMS(text)) != text {
		t.Fatal("UTF16 surrogate pair roundtrip failed")
	}
}
func TestCSRFAndUnauthenticatedConfig(t *testing.T) {
	a := &App{settings: defaults(), sessions: map[string]*Session{}}
	r := httptest.NewRequest("GET", "http://modem/api/settings", nil)
	w := httptest.NewRecorder()
	a.serve(w, r)
	if w.Code != 401 {
		t.Fatal("unauthenticated config exposed")
	}
	r = httptest.NewRequest("POST", "http://modem/api/login", strings.NewReader(`{"password":"fake"}`))
	r.Header.Set("Origin", "http://evil.example")
	r.Header.Set("Content-Type", "application/json")
	w = httptest.NewRecorder()
	a.serve(w, r)
	if w.Code != 403 {
		t.Fatal("cross-origin login accepted")
	}
}

func TestSMSCommandCompletion(t *testing.T) {
	for _, action := range []string{"send", "delete"} {
		t.Run(action, func(t *testing.T) {
			want := "4"
			if action == "delete" {
				want = "6"
			}
			fake := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				r.ParseForm()
				w.Header().Set("Content-Type", "application/json")
				if r.Method == "POST" {
					io.WriteString(w, `{"result":"success"}`)
					return
				}
				if r.Form.Get("cmd") == "loginfo" {
					io.WriteString(w, `{"loginfo":"ok"}`)
					return
				}
				if r.Form.Get("cmd") == "sms_cmd_status_info" {
					if r.Form.Get("sms_cmd") != want {
						t.Error("incorrect B03 command selector")
					}
					io.WriteString(w, `{"sms_cmd_status_result":"3"}`)
					return
				}
				io.WriteString(w, `{"RD":"challenge","wa_inner_version":"a","cr_version":"b"}`)
			}))
			defer fake.Close()
			if e := vendor(fake.URL).smsAction(action, []string{"123"}, "123456789", "test", ""); e != nil {
				t.Fatal(e)
			}
		})
	}
}

func TestVoiceRegistrationSettings(t *testing.T) {
	for _, mode := range []string{"AUTO", "VOLTE", "CS", "VOWIFI"} {
		s := defaults()
		s.VoiceMode = mode
		if err := validate(s); err != nil {
			t.Fatal(err)
		}
		if !strings.Contains(string(gatewayINI(s, t.TempDir())), "voice_mode="+mode+"\n") {
			t.Fatal("missing registration mode")
		}
	}
	s := defaults()
	s.VoiceMode = "UMTS"
	if validate(s) == nil {
		t.Fatal("unsupported registration accepted")
	}
	dir := t.TempDir()
	if err := atomicFile(filepath.Join(dir, "settings.json"), []byte(`{"version":1,"bootstrapSeconds":60,"voiceMode":""}`), 0600); err != nil {
		t.Fatal(err)
	}
	restored, err := readSettings(dir)
	if err != nil || restored.VoiceMode != "AUTO" {
		t.Fatalf("legacy preference: %q %v", restored.VoiceMode, err)
	}
}
