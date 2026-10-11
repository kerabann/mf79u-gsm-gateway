package main

import (
	"encoding/hex"
	"strings"
	"testing"
)

func TestWiFiClientConfig(t *testing.T) {
	if got := hex.EncodeToString(wifiPSK("password", "IEEE")); got != "f42c6fc52df0ebef9ebb4b90b38a5f902e83fe1b135a70e23aed762e9710a12e" {
		t.Fatal("WPA PSK test vector failed")
	}
	w := WiFi{SSID: `a"\b`, Password: `password`, Security: "WPA2"}
	text := wifiClientConfig(w)
	if !strings.Contains(text, "ssid="+hex.EncodeToString([]byte(w.SSID))) || strings.Contains(text, "psk=\"") {
		t.Fatal("unsafe Wi-Fi config")
	}
	for _, required := range []string{"auth_alg=OPEN", "key_mgmt=WPA-PSK", "proto=RSN", "pairwise=CCMP"} {
		if !strings.Contains(text, required) {
			t.Fatal("missing WPA2 station setting: " + required)
		}
	}
	w.Security = "OPEN"
	if strings.Contains(wifiClientConfig(w), "psk=") {
		t.Fatal("password retained for open network")
	}
	s := defaults()
	s.WiFi = WiFi{Mode: "CLIENT", Enabled: true, SSID: "hidden", Password: "password", Security: "WPA2", Network: Network{Mode: "DHCP"}}
	if e := validate(s); e != nil {
		t.Fatal(e)
	}
	s.WiFi.Password = "short"
	if validate(s) == nil {
		t.Fatal("short password accepted")
	}
	s.WiFi.Security = "OPEN"
	s.WiFi.Password = ""
	if e := validate(s); e != nil {
		t.Fatal(e)
	}
	s.WiFi.Mode = "HOTSPOT"
	if validate(s) == nil {
		t.Fatal("open hotspot accepted")
	}
	s.WiFi.Mode = "CLIENT"
	s.WiFi.SSID = "bad\nssid"
	if validate(s) == nil {
		t.Fatal("SSID newline accepted")
	}
}
func TestWiFiScanParser(t *testing.T) {
	text := "bssid / frequency / signal level / flags / ssid\n00:11:22:33:44:55\t2412\t-51\t[WPA2-PSK-CCMP][ESS]\tCafe\\x20WiFi\n00:11:22:33:44:56\t2437\t-65\t[WPA2-PSK-CCMP][ESS]\tCafe\\x20WiFi\n00:11:22:33:44:57\t2462\t-70\t[ESS]\tOpen\n00:11:22:33:44:58\t2412\t-80\t[WPA2-EAP-CCMP][ESS]\tEnterprise\n00:11:22:33:44:59\t2412\t-80\t[ESS]\t\n"
	r := parseWiFiScan(text)
	if len(r) != 3 || r[0].SSID != "Cafe WiFi" || r[0].Security != "WPA2" || r[1].Security != "OPEN" || r[2].Supported {
		t.Fatalf("incorrect scan parsing: %+v", r)
	}
}

func TestWiFiScanAlreadyRunning(t *testing.T) {
	for _, reply := range []string{"OK", "FAIL-BUSY"} {
		if !wifiScanStarted(reply) {
			t.Fatalf("rejected active scan: %s", reply)
		}
	}
	for _, reply := range []string{"FAIL", "", "Could not connect to wpa_supplicant"} {
		if wifiScanStarted(reply) {
			t.Fatalf("accepted failed scan: %s", reply)
		}
	}
}

func TestWiFiUplinkOverlap(t *testing.T) {
	if !wifiNetworksOverlap("192.168.0.50/24", "192.168.0.1/24") || !wifiNetworksOverlap("192.168.1.50/16", "192.168.0.1/24") || wifiNetworksOverlap("192.168.1.50/24", "192.168.0.1/24") || wifiNetworksOverlap("fe80::1/64", "fe80::2/64") {
		t.Fatal("incorrect overlapping LAN detection")
	}
}
func TestWiFiScanGuards(t *testing.T) {
	a := fixtureApp(nil)
	if w := adminRequest(a, "POST", "/api/wifi/scan", "{}", false, false); w.Code != 401 {
		t.Fatal("scan missing auth guard")
	}
	if w := adminRequest(a, "POST", "/api/wifi/scan", "{}", true, false); w.Code != 403 {
		t.Fatal("scan missing CSRF guard")
	}
	if w := adminRequest(a, "GET", "/api/wifi/scan", "", true, false); w.Code != 405 {
		t.Fatal("scan allowed GET mutation")
	}
	a.native = true
	a.pending = "fixture-pending"
	if w := adminRequest(a, "POST", "/api/wifi/scan", "{}", true, true); w.Code != 409 {
		t.Fatal("scan allowed during pending network confirmation")
	}
	a.pending = ""
	a.netmu.Lock()
	w := adminRequest(a, "POST", "/api/wifi/scan", "{}", true, true)
	a.netmu.Unlock()
	if w.Code != 409 {
		t.Fatal("concurrent Wi-Fi apply allowed")
	}
}

func TestWiFiOwnedProcess(t *testing.T) {
	for _, tc := range []struct {
		args  []string
		owned bool
	}{
		{[]string{"udhcpc", "-s", "/dev/mf79u/dhcp.sh", "-i", "wlan0"}, true},
		{[]string{"/sbin/wpa_supplicant", "-c", "/dev/mf79u/wpa.conf"}, true},
		{[]string{"udhcpc", "-s", "/etc/udhcpc.sh"}, false},
		{[]string{"sh", "-c", "/dev/mf79u/dhcp.sh"}, false},
		{[]string{"wpa_supplicant", "-c", "/dev/mf79u/wpa.conf.other"}, false},
	} {
		if wifiOwnedProcess([]byte(strings.Join(tc.args, "\x00")+"\x00")) != tc.owned {
			t.Fatalf("unexpected ownership for %v", tc.args)
		}
	}
}

func TestConfirmedWiFiClient(t *testing.T) {
	p := WiFi{Enabled: true, Mode: "CLIENT", SSID: "fixture"}
	status := map[string]string{"wpa_state": "COMPLETED", "ssid": "fixture", "ip_address": "192.0.2.10"}
	if !confirmedWiFiClient(p, status) {
		t.Fatal("confirmed connection rejected")
	}
	for _, bad := range []map[string]string{
		{"wpa_state": "DISCONNECTED", "ssid": "fixture", "ip_address": "192.0.2.10"},
		{"wpa_state": "COMPLETED", "ssid": "different", "ip_address": "192.0.2.10"},
		{"wpa_state": "COMPLETED", "ssid": "fixture", "ip_address": "0.0.0.0"},
	} {
		if confirmedWiFiClient(p, bad) {
			t.Fatal("stale or unrelated connection accepted")
		}
	}
}
