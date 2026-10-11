package main

import (
	"crypto/pbkdf2"
	"crypto/sha1"
	"errors"
	"net"
	"strconv"
	"strings"
	"time"
)

func wifiPSK(password, ssid string) []byte {
	key, _ := pbkdf2.Key(sha1.New, password, []byte(ssid), 4096, 32)
	return key
}

type WiFiNetwork struct {
	SSID      string `json:"ssid"`
	Signal    int    `json:"signal"`
	Security  string `json:"security"`
	Supported bool   `json:"supported"`
}

func parseWiFiScan(text string) []WiFiNetwork {
	result := []WiFiNetwork{}
	seen := map[string]bool{}
	for _, line := range strings.Split(text, "\n") {
		parts := strings.SplitN(line, "\t", 5)
		if len(parts) != 5 || parts[4] == "" || parts[0] == "bssid" {
			continue
		}
		ssid := decodeScanSSID(parts[4])
		flags := parts[3]
		security := "OPEN"
		supported := true
		if strings.Contains(flags, "WPA2-PSK") && strings.Contains(flags, "CCMP") {
			security = "WPA2"
		} else if strings.Contains(flags, "WPA") || strings.Contains(flags, "WEP") || strings.Contains(flags, "SAE") {
			security = "Unsupported"
			supported = false
		}
		key := ssid + "\x00" + security
		if seen[key] {
			continue
		}
		seen[key] = true
		signal, _ := strconv.Atoi(parts[2])
		result = append(result, WiFiNetwork{ssid, signal, security, supported})
	}
	return result
}
func decodeScanSSID(s string) string {
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		if s[i] == '\\' && i+1 < len(s) {
			if s[i+1] == 'x' && i+3 < len(s) {
				if n, e := strconv.ParseUint(s[i+2:i+4], 16, 8); e == nil {
					b.WriteByte(byte(n))
					i += 3
					continue
				}
			}
			switch s[i+1] {
			case '\\', '"':
				b.WriteByte(s[i+1])
				i++
				continue
			case 'n':
				b.WriteByte('\n')
				i++
				continue
			case 'r':
				b.WriteByte('\r')
				i++
				continue
			case 't':
				b.WriteByte('\t')
				i++
				continue
			case 'e':
				b.WriteByte(27)
				i++
				continue
			}
		}
		b.WriteByte(s[i])
	}
	return b.String()
}

func (a *App) wifiScan(profile WiFi) (networks []WiFiNetwork, err error) {
	// Reuse a running client. Otherwise borrow the radio with a network-free
	// supplicant and restore the confirmed AP/disabled profile before replying.
	existing := profile.Enabled && profile.Mode == "CLIENT"
	if !existing {
		defer func() {
			if e := a.wifiApply(profile); e != nil {
				a.setNetworkError(e)
				err = errors.New("Could not restore Wi-Fi after scan; use USB management")
			}
		}()
		stopWiFiOwned()
		_ = run("brctl", "delif", "bridge0", "wlan0")
		if e := run("ifconfig", "wlan0", "down"); e != nil {
			return nil, e
		}
		if e := prepareRadio(); e != nil {
			return nil, e
		}
		for _, mib := range []string{"opmode=8", "psk_enable=0"} {
			if e := run("iwpriv", "wlan0", "set_mib", mib); e != nil {
				return nil, e
			}
		}
		if e := run("ifconfig", "wlan0", "up"); e != nil {
			return nil, e
		}
		if e := atomicFile("/dev/mf79u/wpa.conf", []byte("ctrl_interface=/dev/mf79u/wpa\nupdate_config=0\n"), 0600); e != nil {
			return nil, e
		}
		if e := run("wpa_supplicant", "-B", "-D", "wext", "-i", "wlan0", "-c", "/dev/mf79u/wpa.conf", "-P", "/dev/mf79u/wifi-wpa.pid"); e != nil {
			return nil, e
		}
	}
	if existing {
		if !strings.Contains(output("wpa_cli", "-p", "/dev/mf79u/wpa", "-i", "wlan0", "status"), "wpa_state=") {
			stopWiFiOwned()
			if e := run("ifconfig", "wlan0", "down"); e != nil {
				return nil, e
			}
			if e := prepareRadio(); e != nil {
				return nil, e
			}
			if e := startWiFiClient(profile); e != nil {
				return nil, e
			}
		}
		// A failed association may leave the Realtek interface down while the
		// owned supplicant and the saved Client profile still exist.
		if e := run("ifconfig", "wlan0", "up"); e != nil {
			return nil, errors.New("Wi-Fi interface could not start; retry scanning")
		}
		if !strings.Contains(output("wpa_cli", "-p", "/dev/mf79u/wpa", "-i", "wlan0", "ap_scan", "1"), "OK") {
			return nil, errors.New("Wi-Fi driver could not enable scanning")
		}
		defer output("wpa_cli", "-p", "/dev/mf79u/wpa", "-i", "wlan0", "ap_scan", "0")
	}
	if !wifiScanStarted(output("wpa_cli", "-p", "/dev/mf79u/wpa", "-i", "wlan0", "scan")) {
		return nil, errors.New("Wi-Fi scan could not start")
	}
	time.Sleep(4 * time.Second)
	text := output("wpa_cli", "-p", "/dev/mf79u/wpa", "-i", "wlan0", "scan_results")
	if !strings.Contains(text, "bssid") {
		return nil, errors.New("Wi-Fi scanner did not return results")
	}
	return parseWiFiScan(text), nil
}

func wifiScanStarted(reply string) bool {
	// ap_scan=1 can already have triggered an automatic scan. The B03
	// supplicant rejects a second request with FAIL-BUSY, but results follow.
	return reply == "OK" || reply == "FAIL-BUSY"
}

// Keep a foreground lease client owned by its explicit PID. The parent only
// waits long enough to fork; renewals continue independently of HTTP requests.
func startWiFiDHCP() error {
	return run("udhcpc", "-b", "-i", "wlan0", "-p", "/dev/mf79u/wifi-dhcp.pid", "-s", "/dev/mf79u/dhcp.sh", "-t", "2", "-T", "2")
}

func wifiNetworksOverlap(a, b string) bool {
	_, first, e := net.ParseCIDR(a)
	if e != nil || first.IP.To4() == nil {
		return false
	}
	_, second, e := net.ParseCIDR(b)
	return e == nil && second.IP.To4() != nil && (first.Contains(second.IP) || second.Contains(first.IP))
}
func (a *App) verifyWiFiUplink() error {
	a.mu.Lock()
	lan, previous := a.settings.LAN.Address, a.applied.LAN.Address
	a.mu.Unlock()
	wlan, e := interfaceByName("wlan0")
	if e != nil {
		return e
	}
	uplinks, e := interfaceAddresses(wlan)
	if e != nil {
		return e
	}
	for _, u := range uplinks {
		if wifiNetworksOverlap(u.String(), lan) {
			return errors.New("Wi-Fi network overlaps the USB management subnet; change the LAN subnet or use another Wi-Fi network")
		}
	}
	// A deliberate LAN change may leave the old recovery alias. Add the new
	// management address before removing only known aliases that clash with STA.
	if e := ensureAddress("bridge0", lan); e != nil {
		return e
	}
	bridge, e := interfaceByName("bridge0")
	if e != nil {
		return e
	}
	local, e := interfaceAddresses(bridge)
	if e != nil {
		return e
	}
	for _, u := range uplinks {
		for _, l := range local {
			if wifiNetworksOverlap(u.String(), l.String()) {
				if l.String() == lan || l.String() != previous && l.String() != "192.168.0.1/24" {
					return errors.New("Wi-Fi network overlaps an existing management address")
				}
				if e := run("ip", "addr", "del", l.String(), "dev", "bridge0"); e != nil {
					return e
				}
			}
		}
	}
	return nil
}

const wifiDHCPHook = `#!/bin/sh
[ "$interface" = wlan0 ] || exit 1
case "$1" in
 deconfig)
  /sbin/ifconfig wlan0 0.0.0.0
  for prefix in 0.0.0.0/1 128.0.0.0/1; do /bin/ip route del "$prefix" dev wlan0 metric 10 2>/dev/null; done
  rm -f /dev/mf79u/resolv.conf
  [ ! -f /dev/mf79u/resolv.before ] || cp /dev/mf79u/resolv.before /tmp/resolv.conf
 ;;
 bound|renew)
  /sbin/ifconfig wlan0 "$ip" netmask "$subnet" || exit 1
  for prefix in 0.0.0.0/1 128.0.0.0/1; do /bin/ip route del "$prefix" dev wlan0 metric 10 2>/dev/null; done
  for gw in $router; do
   for prefix in 0.0.0.0/1 128.0.0.0/1; do /bin/ip route replace "$prefix" via "$gw" dev wlan0 metric 10 || exit 1; done
   break
  done
  : > /dev/mf79u/resolv.conf
  for server in $dns; do echo "nameserver $server" >> /dev/mf79u/resolv.conf; done
  [ ! -s /dev/mf79u/resolv.conf ] || cp /dev/mf79u/resolv.conf /tmp/resolv.conf
 ;;
esac
`

// Realtek's B03 station state can lose association while retaining the lease.
// Reapply only our confirmed Client profile, while idle and outside UI changes.
func (a *App) maintainWiFi() {
	for {
		time.Sleep(30 * time.Second)
		if !a.netmu.TryLock() {
			continue
		}
		a.mu.Lock()
		profile, pending := a.applied.WiFi, a.pending
		a.mu.Unlock()
		status := wifiStatus()
		if pending == "" && confirmedWiFiClient(profile, status) {
			a.mu.Lock()
			if strings.HasPrefix(a.networkError, "Wi-Fi connection failed.") {
				a.networkError = ""
			}
			a.mu.Unlock()
		}
		if pending == "" && profile.Enabled && profile.Mode == "CLIENT" && !gatewayBusy() && status["wpa_state"] != "COMPLETED" {
			if e := a.wifiApply(profile); e != nil {
				a.setNetworkError(e)
			} else {
				a.mu.Lock()
				a.networkError = ""
				a.mu.Unlock()
			}
		}
		a.netmu.Unlock()
	}
}

// A retained DHCP lease alone does not prove that the confirmed profile recovered.
func confirmedWiFiClient(profile WiFi, status map[string]string) bool {
	ip := net.ParseIP(status["ip_address"])
	return profile.Enabled && profile.Mode == "CLIENT" && status["wpa_state"] == "COMPLETED" && status["ssid"] == profile.SSID && ip != nil && !ip.IsUnspecified()
}
