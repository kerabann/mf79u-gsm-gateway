package main

import (
	"crypto/rand"
	"embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"regexp"
	"strings"
	"sync"
	"time"
)

//go:embed web/*
var assets embed.FS
var regexpID = regexp.MustCompile(`^[0-9]{1,9}$`)

type Session struct {
	v         *Vendor
	vendorKey string
	expires   time.Time
	csrf      string
}
type App struct {
	smsIMS               *imsSMSStore
	smsSIP               *smsSIPBridge
	telegram             *telegramSMSBridge
	systemmu             sync.Mutex
	sshmu                sync.Mutex
	sshDone              <-chan error
	sshCmd               *exec.Cmd
	sshProfile, sshError string
	mu                   sync.Mutex
	netmu                sync.Mutex
	fwmu                 sync.Mutex
	sharingEnabled       bool
	settings             Settings
	dir, base            string
	native               bool
	vendorClient         *Vendor
	sessions             map[string]*Session
	bootstrapUntil       time.Time
	networkError         string
	networkNotice        string
	pending              string
	networkReady         bool
	networkRollingBack   bool
	networkDeadline      time.Time
	rollback             *Settings
	applied              Settings
}

func random() string {
	b := make([]byte, 24)
	if _, e := rand.Read(b); e != nil {
		panic(e)
	}
	return hex.EncodeToString(b)
}
func respond(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
func failure(w http.ResponseWriter, status int, e error) {
	respond(w, status, map[string]string{"error": e.Error()})
}
func decode(w http.ResponseWriter, r *http.Request, v any) error {
	r.Body = http.MaxBytesReader(w, r.Body, 65536)
	if !strings.HasPrefix(r.Header.Get("Content-Type"), "application/json") {
		return errors.New("Content-Type must be application/json")
	}
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	if e := d.Decode(v); e != nil {
		return errors.New("Invalid JSON request")
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		return errors.New("Only one JSON object is allowed")
	}
	return nil
}
func (a *App) session(w http.ResponseWriter, r *http.Request) *Session {
	c, e := r.Cookie("mf79u_session")
	if e != nil {
		failure(w, 401, errors.New("Sign in to the interface"))
		return nil
	}
	a.mu.Lock()
	s := a.sessions[c.Value]
	if s != nil && time.Now().Before(s.expires) {
		s.expires = time.Now().Add(30 * time.Minute)
	} else {
		s = nil
		delete(a.sessions, c.Value)
	}
	a.mu.Unlock()
	if s == nil {
		failure(w, 401, errors.New("Session expired. Please sign in again."))
		return nil
	}
	if r.Method != "GET" {
		origin, e := url.Parse(r.Header.Get("Origin"))
		if e != nil || origin.Host != r.Host || origin.Scheme != "http" && origin.Scheme != "https" || r.Header.Get("X-CSRF-Token") != s.csrf {
			failure(w, 403, errors.New("Invalid origin or CSRF token"))
			return nil
		}
	}
	// Match the browser cookie lifetime to the rolling management idle timeout.
	// Polling must not leave an active session with a cookie expiring at login+30m.
	if r.Method == "GET" {
		http.SetCookie(w, &http.Cookie{Name: "mf79u_session", Value: c.Value, Path: "/", HttpOnly: true, SameSite: http.SameSiteStrictMode, MaxAge: 1800})
	}
	return s
}

func (a *App) serve(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("X-Frame-Options", "DENY")
	w.Header().Set("Referrer-Policy", "same-origin")
	w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
	if !strings.HasPrefix(r.URL.Path, "/api/") {
		serveStatic(w, r)
		return
	}
	if r.URL.Path == "/api/login" && r.Method == "POST" {
		origin, e := url.Parse(r.Header.Get("Origin"))
		if e != nil || origin.Host != r.Host {
			failure(w, 403, errors.New("Invalid origin"))
			return
		}
		var req struct {
			Password string `json:"password"`
		}
		if e := decode(w, r, &req); e != nil {
			failure(w, 400, e)
			return
		}
		if len(req.Password) < 1 || len(req.Password) > 256 {
			failure(w, 400, errors.New("Enter the modem password"))
			return
		}
		// B03 rotates its backend session on login. Share its cookie jar so
		// signing in from another UI tab does not invalidate existing tabs.
		a.mu.Lock()
		if a.vendorClient == nil {
			a.vendorClient = vendor(a.base)
		}
		v := a.vendorClient
		a.mu.Unlock()
		vendorKey, e := v.loginWithKey(req.Password)
		req.Password = ""
		if e != nil {
			failure(w, 401, e)
			return
		}
		token, csrf := random(), random()
		a.mu.Lock()
		for k, s := range a.sessions {
			if time.Now().After(s.expires) {
				delete(a.sessions, k)
			}
		}
		if len(a.sessions) >= 8 {
			a.mu.Unlock()
			failure(w, 429, errors.New("Too many sessions"))
			return
		}
		a.sessions[token] = &Session{v: v, vendorKey: vendorKey, expires: time.Now().Add(30 * time.Minute), csrf: csrf}
		a.mu.Unlock()
		http.SetCookie(w, &http.Cookie{Name: "mf79u_session", Value: token, Path: "/", HttpOnly: true, SameSite: http.SameSiteStrictMode, MaxAge: 1800})
		respond(w, 200, map[string]string{"csrf": csrf})
		return
	}
	var s *Session
	if (r.URL.Path == "/api/v1/sms/messages" || strings.HasPrefix(r.URL.Path, "/api/v1/sms/messages/")) && r.Header.Get("Authorization") != "" {
		s = a.smsHeaderSession(w, r)
	} else {
		s = a.session(w, r)
	}
	if s == nil {
		return
	}
	if r.URL.Path == "/api/v1/sms/messages" || strings.HasPrefix(r.URL.Path, "/api/v1/sms/messages/") {
		a.smsREST(w, r, s)
		return
	}
	if strings.HasPrefix(r.URL.Path, "/api/system/") {
		a.system(w, r, s)
		return
	}
	switch r.URL.Path {
	case "/api/session":
		respond(w, 200, map[string]string{"csrf": s.csrf})
	case "/api/logout":
		if r.Method != "POST" {
			w.WriteHeader(405)
			return
		}
		c, _ := r.Cookie("mf79u_session")
		a.mu.Lock()
		delete(a.sessions, c.Value)
		a.mu.Unlock()
		http.SetCookie(w, &http.Cookie{Name: "mf79u_session", Path: "/", MaxAge: -1, HttpOnly: true, SameSite: http.SameSiteStrictMode})
		respond(w, 200, map[string]bool{"ok": true})
	case "/api/settings/credentials":
		if r.Method != "GET" {
			w.WriteHeader(405)
			return
		}
		// Explicit admin-only disclosure for password editing; ordinary settings
		// and status responses continue to omit secrets. Never cache this response.
		if r.Header.Get("X-CSRF-Token") != s.csrf {
			failure(w, 403, errors.New("Invalid CSRF token"))
			return
		}
		a.mu.Lock()
		value := map[string]string{"sipPassword": a.settings.SIP.Password, "sipExtensionPassword": a.settings.SIP.ExtensionPassword, "wifiPassword": a.settings.WiFi.Password}
		a.mu.Unlock()
		respond(w, 200, value)
	case "/api/settings":
		if r.Method == "GET" {
			a.mu.Lock()
			value := publicSettings(a.settings)
			a.mu.Unlock()
			respond(w, 200, value)
			return
		}
		if r.Method != "PUT" {
			w.WriteHeader(405)
			return
		}
		var value Settings
		if e := decode(w, r, &value); e != nil {
			failure(w, 400, e)
			return
		}
		if a.native && value.VoiceMode == "VOWIFI_SMS" && nativeRuntime()["vowifiCellularSmsSupported"] != true {
			failure(w, 409, errors.New("Update the native runtime before enabling VoWiFi with GSM SMS"))
			return
		}
		a.mu.Lock()
		// Webhooks use their own scoped Save; full settings clients preserve them.
		value.Webhooks = a.settings.Webhooks
		if a.pending != "" {
			a.mu.Unlock()
			failure(w, 409, errors.New("Confirm or roll back the network changes first"))
			return
		}
		if value.SIP.Password == "" && value.SIP.PasswordSet {
			value.SIP.Password = a.settings.SIP.Password
		}
		if value.SIP.ExtensionPassword == "" && value.SIP.ExtensionPasswordSet && value.SIP.Extension == a.settings.SIP.Extension {
			value.SIP.ExtensionPassword = a.settings.SIP.ExtensionPassword
		}
		value.SIP.ExtensionPasswordSet = false
		if value.WiFi.Password == "" && value.WiFi.PasswordSet {
			value.WiFi.Password = a.settings.WiFi.Password
		}
		value.SIP.PasswordSet = false
		value.WiFi.PasswordSet = false
		if e := migrateLAN(&value.LAN); e != nil {
			a.mu.Unlock()
			failure(w, 400, e)
			return
		}
		if e := validate(value); e != nil {
			a.mu.Unlock()
			failure(w, 400, e)
			return
		}
		b, _ := json.MarshalIndent(value, "", "  ")
		if e := atomicFile(filepath.Join(a.dir, "settings.json"), b, 0600); e != nil {
			a.mu.Unlock()
			failure(w, 500, errors.New("Could not save settings"))
			return
		}
		a.settings = value
		a.mu.Unlock()
		respond(w, 200, map[string]any{"saved": true, "settings": publicSettings(value)})
	case "/api/webhooks/telegram":
		a.telegramSettings(w, r)
	case "/api/status":
		if r.Method != "GET" {
			w.WriteHeader(405)
			return
		}
		// B03 rotates its short backend session. Reauthenticate once in RAM and
		// retry without exposing or persisting the administrator password.
		radio, e := s.v.status(s.vendorKey, "loginfo,modem_main_state,network_type,network_provider,rssi,lte_rsrp,lte_rsrq,lte_rssi,cell_id,ppp_status,wan_ipaddr,signalbar,simcard_roam,wifi_sta_connection,SSID1,RadioOff,EX_SSID1,EX_ConnectionStatus,EX_StaIP")
		vendorSession := true
		if errors.Is(e, errVendorSession) {
			vendorSession = false
			radio = map[string]any{}
		} else if e != nil {
			failure(w, 502, e)
			return
		}
		wifi := map[string]string{"wpa_state": "DISCONNECTED"}
		if a.native {
			wifi = wifiStatus()
			if wifi["wpa_state"] == "COMPLETED" {
				radio["EX_SSID1"] = wifi["ssid"]
				radio["EX_StaIP"] = wifi["ip_address"]
				radio["wifi_sta_connection"] = "1"
			}
		}
		a.mu.Lock()
		remaining := int(time.Until(a.bootstrapUntil).Seconds())
		if remaining < 0 {
			remaining = 0
		}
		pending, neterr, netnotice, sharing := a.pending, a.networkError, a.networkNotice, a.settings.InternetSharing
		ready, rollingBack := a.networkReady, a.networkRollingBack
		networkRemaining := int(time.Until(a.networkDeadline).Seconds())
		if pending == "" || networkRemaining < 0 {
			networkRemaining = 0
		}
		a.mu.Unlock()
		interfaces := []any{}
		list := networkInterfaces()
		for _, iface := range list {
			if iface.Name == "bridge0" || iface.Name == "wlan0" || iface.Name == "wlan0-vxd" || strings.HasPrefix(iface.Name, "wan") {
				ips, _ := interfaceAddresses(&iface)
				addresses := []string{}
				for _, ip := range ips {
					addresses = append(addresses, ip.String())
				}
				interfaces = append(interfaces, map[string]any{"name": iface.Name, "up": iface.Flags&net.FlagUp != 0, "addresses": addresses})
			}
		}
		runtime := nativeRuntime()
		respond(w, 200, map[string]any{"telegramSMS": a.telegramStatus(), "radio": radio, "vendorSession": vendorSession, "wifi": wifi, "gateway": gatewayStatus(), "runtime": runtime, "interfaces": interfaces, "bootstrapRemaining": remaining, "networkError": neterr, "networkNotice": netnotice, "pendingNetwork": pending, "networkReady": ready, "networkRollingBack": rollingBack, "networkRemaining": networkRemaining, "internetSharing": sharing, "operatorCodecs": []string{"AMR-WB / 23.85 kbit/s max", "AMR-NB fallback"}, "pcmRate": 16000, "hostRelayRequired": runtime["hostRelayRequired"] != false})
	case "/api/apply":
		if r.Method != "POST" {
			w.WriteHeader(405)
			return
		}
		if gatewayBusy() {
			failure(w, 409, errors.New("End the active call before applying settings"))
			return
		}
		var req struct {
			Network bool `json:"network"`
		}
		if e := decode(w, r, &req); e != nil {
			failure(w, 400, e)
			return
		}
		a.mu.Lock()
		value, old := a.settings, a.applied
		if a.pending != "" {
			a.mu.Unlock()
			failure(w, 409, errors.New("Confirm or roll back the previous network changes first"))
			return
		}
		a.mu.Unlock()
		if e := atomicFile(filepath.Join(a.dir, "gateway.ini"), gatewayINI(value, a.dir), 0600); e != nil {
			failure(w, 500, errors.New("Could not write SIP settings"))
			return
		}
		if value.SIP.CA != "" {
			if e := atomicFile(filepath.Join(a.dir, "ca.pem"), []byte(value.SIP.CA), 0600); e != nil {
				failure(w, 500, e)
				return
			}
		}
		warning := ""
		if a.native {
			if !req.Network && sipNeedsReload(value, old) {
				if e := signalGateway(); e != nil {
					warning = e.Error()
				}
			}
			if e := a.applySharing(value.InternetSharing); e != nil {
				failure(w, 500, e)
				return
			}
		}
		token := ""
		if req.Network && a.native {
			deadline := time.Now().Add(90 * time.Second)
			token = random()
			a.mu.Lock()
			a.pending = token
			a.networkError = ""
			a.networkNotice = ""
			a.networkReady = false
			a.networkRollingBack = false
			a.networkDeadline = deadline
			a.rollback = &old
			a.mu.Unlock()
			go func() {
				time.Sleep(time.Second)
				a.applyNetworkChange(token, value, old, deadline)
			}()
		} else {
			a.mu.Lock()
			a.applied = value
			a.mu.Unlock()
		}
		respond(w, 200, map[string]any{"applied": true, "warning": warning, "networkToken": token, "confirmWithin": 90})
	case "/api/network/confirm", "/api/network/rollback":
		if r.Method != "POST" {
			w.WriteHeader(405)
			return
		}
		var req struct {
			Token string `json:"token"`
		}
		if e := decode(w, r, &req); e != nil {
			failure(w, 400, e)
			return
		}
		a.mu.Lock()
		ok := a.pending != "" && a.pending == req.Token
		if ok && r.URL.Path == "/api/network/confirm" && (!a.networkReady || a.networkRollingBack) {
			a.mu.Unlock()
			failure(w, 409, errors.New("Network settings are still being applied"))
			return
		}
		if ok && r.URL.Path == "/api/network/confirm" {
			a.pending = ""
			a.rollback = nil
			a.applied = a.settings
			a.networkError = ""
			a.networkNotice = "Network settings confirmed."
			a.networkReady = false
		}
		a.mu.Unlock()
		if !ok {
			failure(w, 409, errors.New("The network change has already finished"))
			return
		}
		if r.URL.Path == "/api/network/rollback" {
			a.rollbackNetwork(req.Token, "Network changes rolled back.")
		}
		respond(w, 200, map[string]bool{"ok": true})
	case "/api/sms":
		if r.Method != "GET" {
			w.WriteHeader(405)
			return
		}
		storage := r.URL.Query().Get("storage")
		if storage == "" {
			storage = "modem"
		}
		if storage != "modem" && storage != "sim" {
			failure(w, 400, errors.New("SMS storage must be modem or sim"))
			return
		}
		value, e := a.smsList(s.v, storage, s.vendorKey)
		if e != nil {
			a.vendorFailure(w, r, e)
			return
		}
		respond(w, 200, value)
	case "/api/sms/action":
		if r.Method != "POST" {
			w.WriteHeader(405)
			return
		}
		var req struct {
			Action string   `json:"action"`
			IDs    []string `json:"ids"`
			Number string   `json:"number"`
			Text   string   `json:"text"`
		}
		if e := decode(w, r, &req); e != nil {
			failure(w, 400, e)
			return
		}
		if e := a.smsAction(s.v, req.Action, req.IDs, req.Number, req.Text, s.vendorKey); e != nil {
			a.vendorFailure(w, r, e)
			return
		}
		respond(w, 200, map[string]bool{"ok": true})
	case "/api/wifi/scan":
		if r.Method != "POST" {
			w.WriteHeader(405)
			return
		}
		if !a.native {
			respond(w, 200, map[string]any{"networks": []WiFiNetwork{}})
			return
		}
		if gatewayBusy() {
			failure(w, 409, errors.New("Wait until the call ends before scanning Wi-Fi"))
			return
		}
		if !a.netmu.TryLock() {
			failure(w, 409, errors.New("Network settings are being applied"))
			return
		}
		defer a.netmu.Unlock()
		a.mu.Lock()
		profile := a.applied.WiFi
		pending := a.pending
		a.mu.Unlock()
		if pending != "" {
			failure(w, 409, errors.New("Confirm or roll back network settings before scanning"))
			return
		}
		networks, e := a.wifiScan(profile)
		if e != nil {
			failure(w, 502, e)
			return
		}
		respond(w, 200, map[string]any{"networks": networks})
	case "/api/wifi/networks":
		if r.Method != "GET" {
			w.WriteHeader(405)
			return
		}
		value, e := s.v.getAuthenticated(s.vendorKey, "scan_finish,EX_APLIST,EX_APLIST1")
		if e != nil {
			failure(w, 502, e)
			return
		}
		respond(w, 200, value)
	default:
		w.WriteHeader(404)
	}
}

func (a *App) vendorFailure(w http.ResponseWriter, r *http.Request, e error) {
	if errors.Is(e, errVendorSession) {
		// 428 distinguishes the expired stock backend from an expired custom
		// management session (401). Keep settings, IMS and SIP accessible.
		respond(w, http.StatusPreconditionRequired, map[string]any{"error": e.Error(), "vendorSession": false})
		return
	}
	failure(w, 502, e)
}
func (a *App) applyNetworkChange(token string, value, old Settings, deadline time.Time) {
	a.netmu.Lock()
	a.mu.Lock()
	// An immediate rollback can finish during the delayed start, or while this
	// worker waits for another network operation. Never apply its abandoned profile.
	current := a.pending == token && a.rollback != nil
	a.mu.Unlock()
	if !current {
		a.netmu.Unlock()
		return
	}
	var e error
	if !reflect.DeepEqual(value.WiFi, old.WiFi) {
		e = a.wifiApply(value.WiFi)
	}
	if e == nil {
		e = a.lanApply(value.LAN)
	}
	if e == nil {
		e = a.applyVoWiFiUplink(value.VoWiFi)
	}
	if e == nil && sipNeedsReload(value, old) {
		e = signalGateway()
	}
	if e != nil {
		a.setNetworkError(e)
	}
	a.mu.Lock()
	a.networkReady = e == nil
	a.mu.Unlock()
	a.netmu.Unlock()
	if e != nil {
		a.rollbackNetwork(token, "")
		return
	}
	if remaining := time.Until(deadline); remaining > 0 {
		time.Sleep(remaining)
	}
	a.rollbackNetwork(token, "Network changes were not confirmed in time and were rolled back.")
}

func (a *App) rollbackNetwork(token, message string) {
	a.netmu.Lock()
	defer a.netmu.Unlock()
	a.mu.Lock()
	if a.pending != token || a.rollback == nil {
		a.mu.Unlock()
		return
	}
	old, failed := *a.rollback, a.settings
	reason := a.networkError
	a.networkReady = false
	a.networkRollingBack = true
	a.settings.WiFi = old.WiFi
	a.settings.LAN = old.LAN
	a.settings.VoWiFi = old.VoWiFi
	if a.settings.SIP.Role == "SERVER" {
		a.settings.SIP.Bind = strings.SplitN(old.LAN.Address, "/", 2)[0]
	}
	value := a.settings
	a.mu.Unlock()
	var restoreErrors []error
	if a.native {
		// Avoid disconnecting an unchanged uplink when only LAN/DNS changed.
		if !reflect.DeepEqual(failed.WiFi, old.WiFi) {
			restoreErrors = append(restoreErrors, a.wifiApply(old.WiFi))
		}
		restoreErrors = append(restoreErrors, a.lanApply(old.LAN), a.applyVoWiFiUplink(old.VoWiFi))
	}
	restoreErrors = append(restoreErrors, atomicFile(filepath.Join(a.dir, "gateway.ini"), gatewayINI(value, a.dir), 0600))
	if a.native {
		if sipNeedsReload(value, failed) {
			restoreErrors = append(restoreErrors, signalGateway())
		}
		if failed.LAN.Address != old.LAN.Address && failed.LAN.Address != "192.168.0.1/24" {
			restoreErrors = append(restoreErrors, run("ip", "addr", "del", failed.LAN.Address, "dev", "bridge0"))
		}
	}
	b, _ := json.MarshalIndent(value, "", "  ")
	restoreErrors = append(restoreErrors, atomicFile(filepath.Join(a.dir, "settings.json"), b, 0600))
	a.mu.Lock()
	defer a.mu.Unlock()
	a.pending = ""
	a.rollback = nil
	a.networkRollingBack = false
	// Network rollback preserves separately applied SIP/mobile settings.
	a.applied = value
	a.networkNotice = message
	if e := errors.Join(restoreErrors...); e != nil {
		a.networkError = "Could not fully restore the previous network settings. Check Network and Wi-Fi settings."
		return
	}
	if reason != "" {
		a.networkError = strings.TrimSuffix(reason, ".") + ". Network changes rolled back; USB management is still available."
	} else {
		a.networkError = ""
	}
}
func main() {
	addr := flag.String("listen", "0.0.0.0:18080", "management HTTP address")
	dir := flag.String("data", "/mnt/userdata/mf79u", "settings directory")
	base := flag.String("vendor", "http://127.0.0.1", "local vendor service")
	native := flag.Bool("native", false, "enable modem service and network controls")
	boot := flag.Bool("bootstrap", false, "apply the saved Wi-Fi profile")
	telegramCheck := flag.Bool("telegram-diagnose", false, "read-only Telegram DNS/TLS/bot/chat diagnostic; no message submission")
	smsReceiveCheck := flag.Bool("sms-receive-diagnose", false, "read-only incoming SMS concatenation metadata; no message fields or submission")
	flag.Parse()
	// This vendor Linux 3.4 kernel has a non-standard syscall 384: Go's
	// getrandom probe does not return ENOSYS. Use the kernel CSPRNG device.
	if *native {
		f, err := os.Open("/dev/urandom")
		if err != nil {
			log.Fatal("Kernel CSPRNG unavailable")
		}
		rand.Reader = f
	}
	if *telegramCheck {
		_ = json.NewEncoder(os.Stdout).Encode(telegramDiagnostics(*dir))
		return
	}
	if *smsReceiveCheck {
		_ = json.NewEncoder(os.Stdout).Encode(smsReceiveDiagnostics(*base))
		return
	}
	s, e := readSettings(*dir)
	if e != nil {
		log.Fatal("Invalid persisted settings")
	}
	var hotspotError error
	if *native {
		if e := factoryHotspot(&s); e != nil {
			hotspotError = errors.New("Secure hotspot profile unavailable; configure Wi-Fi using USB")
			s.WiFi.Enabled = false
		}
	}
	a := &App{settings: s, applied: s, dir: *dir, base: *base, native: *native, sessions: make(map[string]*Session)}
	if hotspotError != nil {
		a.networkError = hotspotError.Error()
	}
	if *native {
		if e := webAccess(); e != nil {
			a.networkError = e.Error()
		}
		if e := a.applySharing(s.InternetSharing); e != nil {
			a.networkError = e.Error()
		}
		go maintainWiFiDNS()
		go a.maintainWiFi()
		go a.maintainFirewall()
		go a.maintainLAN()
		go a.maintainSSH()
	}
	if *boot {
		go func() {
			a.bootstrap()
			a.netmu.Lock()
			defer a.netmu.Unlock()
			a.mu.Lock()
			saved := a.settings
			a.mu.Unlock()
			if e := a.lanApply(saved.LAN); e != nil {
				a.setNetworkError(e)
			}
		}()
	}
	srv := http.Server{Addr: *addr, Handler: http.HandlerFunc(a.serve), ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 15 * time.Second, WriteTimeout: 30 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 8192, ErrorLog: log.New(os.Stderr, "http: ", 0)}
	fmt.Println("MF79U control 0.10 listening")
	listener, e := net.Listen("tcp4", *addr)
	if e != nil {
		log.Fatal(e)
	}
	if *native {
		if e := a.startSMSIMS(); e != nil {
			fmt.Println("SMS_IMS_STORE_FAILED")
		}
		if e := a.startSMSSIP(); e != nil {
			fmt.Println("SMS_SIP_START_FAILED") // No socket errors or private data.
		}
		if e := a.startTelegramSMS(); e != nil {
			fmt.Println("TELEGRAM_SMS_START_FAILED")
		}
	}
	if e := srv.Serve(listener); e != nil {
		log.Fatal(e)
	}
}
