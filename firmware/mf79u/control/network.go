package main

import (
	"context"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"strconv"
	"strings"
	"syscall"
	"time"
)

func run(args ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	// Output may include credentials on failure; deliberately discard it.
	if e := exec.CommandContext(ctx, args[0], args[1:]...).Run(); e != nil {
		return fmt.Errorf("Could not run %s", filepath.Base(args[0]))
	}
	return nil
}
func output(args ...string) string {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	b, _ := exec.CommandContext(ctx, args[0], args[1:]...).Output()
	return strings.TrimSpace(string(b))
}
func gatewayStatus() map[string]any {
	r := map[string]any{"running": false, "imsReady": false, "activeCall": false}
	b, e := os.ReadFile("/dev/.mf79u-gateway-status.json")
	if e == nil {
		json.Unmarshal(b, &r)
		pid, _ := r["pid"].(float64)
		exe, _ := os.Readlink(fmt.Sprintf("/proc/%d/exe", int(pid)))
		if filepath.Base(exe) != ".mf79u-sip-gateway" && filepath.Base(exe) != "mf79u-sip-gateway" {
			return map[string]any{"running": false, "imsReady": false, "activeCall": false}
		}
		if pid < 2 || syscall.Kill(int(pid), 0) != nil {
			return map[string]any{"running": false, "imsReady": false, "activeCall": false}
		}
	}
	return r
}
func gatewayBusy() bool {
	if gatewayStatus()["activeCall"] == true {
		return true
	}
	owner, _ := nativeRuntime()["callBackend"].(string)
	return owner == "ims" || owner == "cs"
}
func nativeRuntime() map[string]any {
	r := map[string]any{"hostRelayRequired": true}
	b, e := os.ReadFile("/dev/.mf79u-native-status.json")
	if e != nil || json.Unmarshal(b, &r) != nil {
		return map[string]any{"hostRelayRequired": true}
	}
	pid, _ := r["pid"].(float64)
	exe, _ := os.Readlink(fmt.Sprintf("/proc/%d/exe", int(pid)))
	name := filepath.Base(exe)
	if pid < 2 || syscall.Kill(int(pid), 0) != nil ||
		name != ".mf79u-native-gateway" && name != "mf79u-native-gateway" {
		return map[string]any{"hostRelayRequired": true}
	}
	// Autonomous SMS service is useful before IMS, including GSM roaming.
	// A stopped controller or absent SIP process is still not readiness proof.
	state, _ := r["state"].(string)
	sipPID, _ := r["sipPid"].(float64)
	r["hostRelayRequired"] = !((state == "ready" && (r["imsReady"] == true || r["voiceReady"] == true) ||
		(state == "sms_only" || state == "registering") && r["smsOnly"] == true) &&
		sipPID >= 2 && gatewayStatus()["running"] == true)
	return r
}
func signalGateway() error {
	if gatewayStatus()["version"] != "0.8" {
		return errors.New("Start SIP gateway 0.8 to apply these settings. The current process is still running.")
	}
	entries, _ := os.ReadDir("/proc")
	for _, entry := range entries {
		if _, e := strconv.Atoi(entry.Name()); e != nil {
			continue
		}
		exe, e := os.Readlink("/proc/" + entry.Name() + "/exe")
		if e != nil {
			continue
		}
		if filepath.Base(exe) == ".mf79u-sip-gateway" || filepath.Base(exe) == "mf79u-sip-gateway" {
			pid, _ := strconv.Atoi(entry.Name())
			return syscall.Kill(pid, syscall.SIGHUP)
		}
	}
	return errors.New("The SIP gateway is not running. Settings are saved for the next start.")
}
func sharing(enabled bool) error {
	for _, tool := range []string{"iptables", "ip6tables"} {
		if _, e := exec.LookPath(tool); e != nil {
			if tool == "ip6tables" {
				continue
			}
			return e
		}
		_ = run(tool, "-N", "MF79U_SHARE")
		if e := run(tool, "-F", "MF79U_SHARE"); e != nil {
			return e
		}
		_ = run(tool, "-N", "MF79U_DATA")
		if e := run(tool, "-F", "MF79U_DATA"); e != nil {
			return e
		}
		if !enabled {
			// All cellular forwarding is blocked. Local IMS/SIP/SMS use INPUT/OUTPUT.
			for _, direction := range [][]string{{"-o", "wan+"}, {"-i", "wan+"}} {
				args := append([]string{tool, "-A", "MF79U_SHARE"}, direction...)
				target := "REJECT"
				if tool == "ip6tables" {
					target = "DROP"
				} // Vendor kernel has no IPv6 REJECT target.
				args = append(args, "-j", target)
				if e := run(args...); e != nil {
					return e
				}
			}
			// Keep only the dedicated operator IMS bearer. SIP to an external
			// PBX must then use USB, not the ordinary cellular internet bearer.
			if e := run(tool, "-A", "MF79U_DATA", "-o", "wan5", "-j", "RETURN"); e != nil {
				return e
			}
			target := "REJECT"
			if tool == "ip6tables" {
				target = "DROP"
			}
			if e := run(tool, "-A", "MF79U_DATA", "-o", "wan+", "-j", target); e != nil {
				return e
			}
		}
		_ = run(tool, "-D", "FORWARD", "-j", "MF79U_SHARE")
		if e := run(tool, "-I", "FORWARD", "1", "-j", "MF79U_SHARE"); e != nil {
			return e
		}
		_ = run(tool, "-D", "OUTPUT", "-j", "MF79U_DATA")
		if e := run(tool, "-I", "OUTPUT", "1", "-j", "MF79U_DATA"); e != nil {
			return e
		}
	}
	return nil
}

func (a *App) applySharing(enabled bool) error {
	a.fwmu.Lock()
	defer a.fwmu.Unlock()
	if e := sharing(enabled); e != nil {
		return e
	}
	a.sharingEnabled = enabled
	return nil
}

// The vendor radio service rebuilds firewall tables after SIM registration
// and bridge changes. Reconcile only our rules; never replace vendor tables.
func firewallIntact(filter, nat, filter6 string, sharingEnabled bool) bool {
	normalize := func(value string) []string {
		lines := []string{}
		for _, line := range strings.Split(value, "\n") {
			lines = append(lines, strings.Join(strings.Fields(line), " "))
		}
		return lines
	}
	has := func(lines []string, rule string) bool {
		for _, line := range lines {
			if line == rule || strings.HasPrefix(line, rule+" ") {
				return true
			}
		}
		return false
	}
	first := func(lines []string, chain, rule string) bool {
		for _, line := range lines {
			if strings.HasPrefix(line, "-A "+chain+" ") {
				return line == rule
			}
		}
		return false
	}
	for _, pair := range []struct{ value, target string }{{filter, "REJECT"}, {filter6, "DROP"}} {
		if pair.value == "" {
			return false
		}
		lines := normalize(pair.value)
		if !first(lines, "INPUT", "-A INPUT -j MF79U_WEB") || !first(lines, "FORWARD", "-A FORWARD -j MF79U_SHARE") || !first(lines, "OUTPUT", "-A OUTPUT -j MF79U_DATA") {
			return false
		}
		if has(lines, "-A MF79U_DATA -o wan+ -j "+pair.target) == sharingEnabled {
			return false
		}
		if !sharingEnabled && (!has(lines, "-A MF79U_DATA -o wan5 -j RETURN") || !first(lines, "MF79U_DATA", "-A MF79U_DATA -o wan5 -j RETURN")) {
			return false
		}
		for _, port := range []string{"80", "18080"} {
			if !has(lines, "-A MF79U_WEB -i wan+ -p tcp -m tcp --dport "+port+" -j "+pair.target) {
				return false
			}
		}
		for _, direction := range []string{"-o", "-i"} {
			present := has(lines, "-A MF79U_SHARE "+direction+" wan+ -j "+pair.target)
			if present == sharingEnabled {
				return false
			}
		}
	}
	lines := normalize(nat)
	for _, iface := range []string{"bridge0", "wlan0", "wlan0-vxd"} {
		if !has(lines, "-A PREROUTING -i "+iface+" -p tcp -m tcp --dport 80 -j REDIRECT --to-ports 18080") {
			return false
		}
	}

	if !has(strings.Split(filter, "\n"), "-A MF79U_WEB -p tcp -m tcp --dport 22 -j REJECT") || !has(strings.Split(filter6, "\n"), "-A MF79U_WEB -p tcp -m tcp --dport 22 -j DROP") {
		return false
	}
	for _, iface := range []string{"bridge0", "wlan0", "wlan0-vxd", "lo"} {
		if !has(strings.Split(filter, "\n"), "-A MF79U_WEB -i "+iface+" -p tcp -m tcp --dport 22 -j ACCEPT") {
			return false
		}
	}
	return true
}

func (a *App) maintainFirewall() {
	for range time.NewTicker(3 * time.Second).C {
		// B03 can recreate its USB interface without restoring bridge membership.
		// Keep the existing LAN address and restore only our USB management link.
		if e := ensureUSBLAN(); e != nil {
			a.setNetworkError(e)
		}
		a.fwmu.Lock()
		filter, nat := output("iptables", "-S"), output("iptables", "-t", "nat", "-S")
		filter6 := output("ip6tables", "-S")
		if !firewallIntact(filter, nat, filter6, a.sharingEnabled) {
			webErr, sharingErr := webAccess(), sharing(a.sharingEnabled)
			if webErr != nil {
				a.setNetworkError(webErr)
			} else if sharingErr != nil {
				a.setNetworkError(sharingErr)
			} else {
				a.clearFirewallError()
			}
		} else {
			a.clearFirewallError()
		}
		a.fwmu.Unlock()
	}
}

func (a *App) clearFirewallError() {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.networkError == "Could not run iptables" || a.networkError == "Could not run ip6tables" {
		a.networkError = ""
	}
}
func wifiOwnedProcess(cmd []byte) bool {
	args := strings.Split(strings.TrimRight(string(cmd), "\x00"), "\x00")
	if len(args) == 0 {
		return false
	}
	program := filepath.Base(args[0])
	for i := 1; i+1 < len(args); i++ {
		if program == "udhcpc" && args[i] == "-s" && args[i+1] == "/dev/mf79u/dhcp.sh" {
			return true
		}
		if program == "wpa_supplicant" && args[i] == "-c" && args[i+1] == "/dev/mf79u/wpa.conf" {
			return true
		}
	}
	return false
}
func stopWiFiOwned() {
	entries, _ := os.ReadDir("/proc")
	for _, entry := range entries {
		pid, e := strconv.Atoi(entry.Name())
		if e != nil || pid <= 1 {
			continue
		}
		path := fmt.Sprintf("/proc/%d/cmdline", pid)
		cmd, _ := os.ReadFile(path)
		if !wifiOwnedProcess(cmd) {
			continue
		}
		_ = syscall.Kill(pid, syscall.SIGTERM)
		for i := 0; i < 20; i++ {
			current, _ := os.ReadFile(path)
			if string(current) != string(cmd) {
				break
			}
			time.Sleep(50 * time.Millisecond)
		}
		current, _ := os.ReadFile(path)
		if string(current) == string(cmd) {
			_ = syscall.Kill(pid, syscall.SIGKILL)
		}
	}
	for _, name := range []string{"wifi-wpa.pid", "wifi-dhcp.pid"} {
		_ = os.Remove("/dev/mf79u/" + name)
	}
}
func (a *App) wifiApply(w WiFi) error {
	stopWiFiOwned()
	stopOwnedPID("bootstrap-dhcp.pid")
	_ = os.Remove("/dev/mf79u/wpa.conf")
	_ = os.Remove("/dev/mf79u/resolv.conf")
	if e := os.MkdirAll("/dev/mf79u", 0700); e != nil {
		return e
	}
	// Remove only routes and addresses from the former owned station mode.
	for _, prefix := range []string{"default", "0.0.0.0/1", "128.0.0.0/1"} {
		_ = run("ip", "route", "del", prefix, "dev", "wlan0", "metric", "10")
	}
	_ = run("ip", "addr", "flush", "dev", "wlan0", "scope", "global")
	if old, e := os.ReadFile("/dev/mf79u/resolv.before"); e == nil {
		_ = atomicFile("/tmp/resolv.conf", old, 0644)
		_ = os.Remove("/dev/mf79u/resolv.before")
	}
	_ = run("brctl", "delif", "bridge0", "wlan0")
	if e := run("ifconfig", "wlan0", "down"); e != nil {
		return e
	}
	if !w.Enabled {
		mode := "opmode=16"
		if w.Mode == "CLIENT" {
			mode = "opmode=8"
		}
		return run("iwpriv", "wlan0", "set_mib", mode)
	}
	if e := prepareRadio(); e != nil {
		return e
	}
	if w.Mode == "CLIENT" {
		return a.wifiClientApply(w)
	}
	for _, mib := range []string{"opmode=16", "ssid=" + w.SSID, "hiddenAP=" + strconv.Itoa(btoi(w.Hidden)), "authtype=0", "encmode=2", "802_1x=1", "psk_enable=2", "wpa_cipher=8", "wpa2_cipher=8", "passphrase=" + w.Password} {
		if e := run("iwpriv", "wlan0", "set_mib", mib); e != nil {
			return e
		}
	}
	if e := verifyHotspotSecurity(w.Password); e != nil {
		return e
	}
	if e := run("ifconfig", "wlan0", "up"); e != nil {
		return e
	}
	if e := verifyHotspotSecurity(w.Password); e != nil {
		_ = run("ifconfig", "wlan0", "down")
		return e
	}
	// Membership may already exist in the vendor bridge.
	if !strings.Contains(output("brctl", "show", "bridge0"), "wlan0") {
		if e := run("brctl", "addif", "bridge0", "wlan0"); e != nil {
			_ = run("ifconfig", "wlan0", "down")
			return e
		}
	}
	if e := a.apDHCP(); e != nil {
		_ = run("ifconfig", "wlan0", "down")
		return e
	}
	return nil
}

func (a *App) wifiClientApply(w WiFi) error {
	if e := startWiFiClient(w); e != nil {
		return e
	}
	// B03's vendor connection script selects with ap_scan=1 then returns
	// control to its driver with ap_scan=0. Generic WEXT defaults do not join.
	for _, args := range [][]string{{"sta_autoconnect", "0"}, {"ap_scan", "1"}, {"select_network", "0"}} {
		if !strings.Contains(output(append([]string{"wpa_cli", "-p", "/dev/mf79u/wpa", "-i", "wlan0"}, args...)...), "OK") {
			return errors.New("Wi-Fi driver could not select the network")
		}
	}
	time.Sleep(3 * time.Second)
	if !strings.Contains(output("wpa_cli", "-p", "/dev/mf79u/wpa", "-i", "wlan0", "ap_scan", "0"), "OK") {
		return errors.New("Wi-Fi driver could not start association")
	}
	return a.finishWiFiClient(w)
}

func startWiFiClient(w WiFi) error {
	if e := run("iwpriv", "wlan0", "set_mib", "opmode=8"); e != nil {
		return e
	}
	if e := run("iwpriv", "wlan0", "set_mib", "psk_enable=0"); e != nil {
		return e
	}
	if e := run("ifconfig", "wlan0", "up"); e != nil {
		return e
	}
	text := wifiClientConfig(w)
	if e := atomicFile("/dev/mf79u/wpa.conf", []byte(text), 0600); e != nil {
		return e
	}
	if e := run("wpa_supplicant", "-B", "-D", "wext", "-i", "wlan0", "-c", "/dev/mf79u/wpa.conf", "-P", "/dev/mf79u/wifi-wpa.pid"); e != nil {
		return e
	}
	return nil
}

func (a *App) finishWiFiClient(w WiFi) error {
	deadline := time.Now().Add(35 * time.Second)
	for !strings.Contains(output("wpa_cli", "-p", "/dev/mf79u/wpa", "-i", "wlan0", "status"), "wpa_state=COMPLETED") {
		if time.Now().After(deadline) {
			return errors.New("Wi-Fi connection failed. Check the SSID, password and signal strength.")
		}
		time.Sleep(time.Second)
	}
	if w.Network.Mode == "STATIC" {
		if e := ensureAddress("wlan0", w.Network.Address); e != nil {
			return e
		}
		if e := a.verifyWiFiUplink(); e != nil {
			return e
		}
		if w.Network.Gateway != "" {
			// More-specific routes prefer Wi-Fi without deleting cellular defaults.
			// IMS sockets remain bound to wan5, with their bearer routes intact.
			for _, prefix := range []string{"0.0.0.0/1", "128.0.0.0/1"} {
				if e := run("ip", "route", "replace", prefix, "via", w.Network.Gateway, "dev", "wlan0", "metric", "10"); e != nil {
					return e
				}
			}
		}
		if len(w.Network.DNS) > 0 {
			var text strings.Builder
			for _, d := range w.Network.DNS {
				text.WriteString("nameserver " + d + "\n")
			}
			if e := setDNS([]byte(text.String())); e != nil {
				return e
			}
		}
	} else {
		if _, e := os.Stat("/dev/mf79u/resolv.before"); os.IsNotExist(e) {
			b, _ := os.ReadFile("/tmp/resolv.conf")
			if e = atomicFile("/dev/mf79u/resolv.before", b, 0600); e != nil {
				return e
			}
		}
		script := []byte(wifiDHCPHook)
		if e := atomicFile("/dev/mf79u/dhcp.sh", script, 0700); e != nil {
			return e
		}
		if e := startWiFiDHCP(); e != nil {
			return e
		}
		deadline = time.Now().Add(15 * time.Second)
		for {
			iface, e := interfaceByName("wlan0")
			ready := false
			if e == nil {
				ips, _ := interfaceAddresses(iface)
				for _, s := range ips {
					ip, _, _ := net.ParseCIDR(s.String())
					if ip.To4() != nil {
						ready = true
					}
				}
			}
			if ready {
				if e := a.verifyWiFiUplink(); e != nil {
					return e
				}
				break
			}
			if time.Now().After(deadline) {
				return errors.New("Wi-Fi DHCP did not provide an IPv4 address")
			}
			time.Sleep(time.Second)
		}
	}
	return nil
}

// B03 iwpriv returns raw decimal bytes, including trailing struct padding. Its driver
// handles WPA2-PSK in-kernel (vendor wlanapp excludes auth for pure PSK APs).
func mibBytes(value string) ([]byte, error) {
	_, raw, ok := strings.Cut(value, "get_mib:")
	if !ok {
		return nil, errors.New("Missing Wi-Fi MIB response")
	}
	var data []byte
	for _, field := range strings.Fields(raw) {
		b, e := strconv.ParseUint(field, 10, 8)
		if e != nil {
			return nil, errors.New("Invalid Wi-Fi MIB response")
		}
		data = append(data, byte(b))
	}
	if len(data) == 0 {
		return nil, errors.New("Empty Wi-Fi MIB response")
	}
	return data, nil
}
func hotspotSecurityMatches(read func(string) string, password string) bool {
	for name, wanted := range map[string]byte{"encmode": 2, "802_1x": 1, "psk_enable": 2, "wpa2_cipher": 8} {
		data, e := mibBytes(read(name))
		if e != nil || data[0] != wanted {
			return false
		}
		for _, b := range data[1:] {
			if b != 0 {
				return false
			}
		}
	}
	data, e := mibBytes(read("passphrase"))
	return e == nil && strings.SplitN(string(data), "\x00", 2)[0] == password
}
func verifyHotspotSecurity(password string) error {
	if !hotspotSecurityMatches(func(name string) string { return output("iwpriv", "wlan0", "get_mib", name) }, password) {
		return errors.New("WPA2 protection could not be verified; hotspot is disabled")
	}
	return nil
}

func wifiStatus() map[string]string {
	r := map[string]string{"mode": "HOTSPOT", "state": "DISABLED"}
	if data, e := mibBytes(output("iwpriv", "wlan0", "get_mib", "opmode")); e == nil && data[0]&8 != 0 {
		r["mode"] = "CLIENT"
		if !strings.Contains(output("ifconfig", "wlan0"), "UP BROADCAST") {
			r["wpa_state"] = "DISCONNECTED"
			return r
		}
		r["wpa_state"] = "DISCONNECTED"
		r["state"] = "DISCONNECTED"
		for _, line := range strings.Split(output("wpa_cli", "-p", "/dev/mf79u/wpa", "-i", "wlan0", "status"), "\n") {
			k, v, ok := strings.Cut(line, "=")
			if ok && (k == "wpa_state" || k == "ssid" || k == "ip_address" || k == "bssid") {
				r[k] = v
			}
		}
		r["state"] = r["wpa_state"]
	} else if strings.Contains(output("ifconfig", "wlan0"), "UP BROADCAST") {
		r["state"] = "ENABLED"
	}
	return r
}
func wifiClientConfig(w WiFi) string {
	// Hex SSID and derived PSK avoid config injection, including quotes/backslashes.
	text := "ctrl_interface=/dev/mf79u/wpa\nupdate_config=0\nnetwork={\n scan_ssid=1\n auth_alg=OPEN\n ssid=" + hex.EncodeToString([]byte(w.SSID)) + "\n"
	if w.Security == "OPEN" {
		text += " key_mgmt=NONE\n"
	} else {
		text += " key_mgmt=WPA-PSK\n proto=RSN\n pairwise=CCMP\n psk=" + hex.EncodeToString(wifiPSK(w.Password, w.SSID)) + "\n"
	}
	return text + "}\n"
}
func maintainWiFiDNS() {
	for {
		time.Sleep(10 * time.Second)
		if _, e := os.Stat("/dev/mf79u/vowifi-usb-ready"); e == nil {
			continue
		}
		if !strings.Contains(output("ip", "route", "show", "0.0.0.0/1"), "dev wlan0") {
			continue
		}
		wanted, e := os.ReadFile("/dev/mf79u/resolv.conf")
		if e != nil || len(wanted) == 0 {
			continue
		}
		current, _ := os.ReadFile("/tmp/resolv.conf")
		if string(current) != string(wanted) {
			_ = atomicFile("/tmp/resolv.conf", wanted, 0644)
		}
	}
}
func (a *App) lanApply(n Network) error {
	if e := ensureUSBLAN(); e != nil {
		return e
	}
	// Keep the existing USB management address as a recovery alias. The B03
	// kernel rejects RTM_NEWADDR with NLM_F_REPLACE, so use idempotent add.
	if e := ensureAddress("bridge0", n.Address); e != nil {
		return e
	}
	a.mu.Lock()
	w := a.settings.WiFi
	a.mu.Unlock()
	if w.Enabled && w.Mode == "CLIENT" {
		if e := a.verifyWiFiUplink(); e != nil {
			return e
		}
	}
	return a.lanDHCP(n)
}

func ensureUSBLAN() error {
	if _, e := os.Stat("/sys/class/net/usblan0"); e != nil {
		return nil // USB may not be connected at boot.
	}
	if _, e := os.Stat("/sys/class/net/bridge0/brif/usblan0"); e == nil {
		return nil
	}
	return run("brctl", "addif", "bridge0", "usblan0")
}

func ensureAddress(device, address string) error {
	ip, network, e := net.ParseCIDR(address)
	if e != nil {
		return e
	}
	prefix, _ := network.Mask.Size()
	canonical := fmt.Sprintf("%s/%d", ip.String(), prefix)
	iface, e := interfaceByName(device)
	if e != nil {
		return e
	}
	addresses, e := interfaceAddresses(iface)
	if e != nil {
		return e
	}
	for _, existing := range addresses {
		if existing.String() == canonical {
			return nil
		}
	}
	return run("ip", "addr", "add", canonical, "dev", device)
}

// B03 can reject Go's netlink dumps. The vendor ip utility can still read
// addresses; use it when the Go query fails.
func interfaceAddresses(iface *net.Interface) ([]net.Addr, error) {
	addresses, e := iface.Addrs()
	if e == nil {
		return addresses, nil
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	b, e := exec.CommandContext(ctx, "ip", "addr", "show", "dev", iface.Name).Output()
	if e != nil {
		return nil, errors.New("Could not read interface addresses")
	}
	return parseInterfaceAddresses(string(b)), nil
}

func parseInterfaceAddresses(text string) []net.Addr {
	addresses := []net.Addr{}
	for _, line := range strings.Split(text, "\n") {
		f := strings.Fields(line)
		if len(f) < 2 || (f[0] != "inet" && f[0] != "inet6") {
			continue
		}
		ip, subnet, e := net.ParseCIDR(f[1])
		if e == nil {
			subnet.IP = ip
			addresses = append(addresses, subnet)
		}
	}
	return addresses
}

func interfaceByName(name string) (*net.Interface, error) {
	iface, e := net.InterfaceByName(name)
	if e == nil {
		return iface, nil
	}
	if name == "" || filepath.Base(name) != name {
		return nil, errors.New("Invalid interface name")
	}
	base := filepath.Join("/sys/class/net", name)
	index, e := os.ReadFile(filepath.Join(base, "ifindex"))
	if e != nil {
		return nil, errors.New("Interface unavailable")
	}
	n, e := strconv.Atoi(strings.TrimSpace(string(index)))
	if e != nil {
		return nil, e
	}
	mac, _ := os.ReadFile(filepath.Join(base, "address"))
	hw, _ := net.ParseMAC(strings.TrimSpace(string(mac)))
	flags, _ := os.ReadFile(filepath.Join(base, "flags"))
	bits, _ := strconv.ParseUint(strings.TrimSpace(string(flags)), 0, 32)
	iface = &net.Interface{Name: name, Index: n, HardwareAddr: hw}
	if bits&syscall.IFF_UP != 0 {
		iface.Flags |= net.FlagUp
	}
	return iface, nil
}

func networkInterfaces() []net.Interface {
	interfaces, e := net.Interfaces()
	if e == nil {
		return interfaces
	}
	entries, _ := os.ReadDir("/sys/class/net")
	for _, entry := range entries {
		if iface, e := interfaceByName(entry.Name()); e == nil {
			interfaces = append(interfaces, *iface)
		}
	}
	return interfaces
}

// Migrate to the protected device AP profile, never to old station credentials.
func factoryHotspot(s *Settings) error {
	if s.WiFi.Mode == "CLIENT" || s.WiFi.Mode == "HOTSPOT" && s.WiFi.SSID != "" {
		return nil
	}
	ssid := output("nv", "get", "SSID1")
	key, err := base64.StdEncoding.DecodeString(output("nv", "get", "WPAPSK1_encode"))
	if err != nil || len(ssid) < 1 || len([]byte(ssid)) > 32 || len(key) < 8 || len(key) > 63 || strings.ContainsAny(ssid+string(key), "\x00\r\n") {
		return errors.New("No valid secure hotspot profile found on the device")
	}
	s.WiFi = WiFi{Mode: "HOTSPOT", Enabled: true, SSID: ssid, Password: string(key), Security: "WPA2", Network: Network{Mode: "DHCP"}}
	for i := range key {
		key[i] = 0
	}
	return nil
}
func (a *App) bootstrap() {
	if !a.native {
		return
	}
	a.netmu.Lock()
	defer a.netmu.Unlock()
	a.mu.Lock()
	w := a.settings.WiFi
	uplink := a.settings.VoWiFi
	a.bootstrapUntil = time.Time{}
	a.mu.Unlock()
	if uplink.Uplink == "USB" {
		if e := a.applyVoWiFiUplink(uplink); e != nil {
			a.setNetworkError(e)
		}
	}
	// Early vendor WLAN/router startup can drop association during DHCP.
	// Retry only this boot profile, once, while idle; USB IMS can run meanwhile.
	e := a.wifiApply(w)
	if e != nil && w.Mode == "CLIENT" && w.Enabled {
		time.Sleep(5 * time.Second)
		a.mu.Lock()
		unchanged := reflect.DeepEqual(a.settings.WiFi, w)
		a.mu.Unlock()
		if unchanged && !gatewayBusy() {
			e = a.wifiApply(w)
		}
	}
	if e != nil {
		a.setNetworkError(e)
	}
	if e := a.applyVoWiFiUplink(uplink); e != nil {
		a.setNetworkError(e)
	}
}

func prepareRadio() error {
	iface, e := interfaceByName("bridge0")
	if e != nil || len(iface.HardwareAddr) != 6 {
		return errors.New("Management MAC address unavailable")
	}
	mac := append(net.HardwareAddr(nil), iface.HardwareAddr...)
	mac[0] = (mac[0] | 2) & 0xfe
	mac[5] ^= 1
	if e = run("ifconfig", "wlan0", "hw", "ether", mac.String()); e != nil {
		return e
	}
	for _, mib := range []string{"func_off=0", "vap_enable=0"} {
		if e = run("iwpriv", "wlan0", "set_mib", mib); e != nil {
			return e
		}
	}
	return nil
}
func stopOwnedPID(name string) {
	b, e := os.ReadFile("/dev/mf79u/" + name)
	if e != nil {
		return
	}
	pid, _ := strconv.Atoi(strings.TrimSpace(string(b)))
	if pid > 1 {
		cmd, _ := os.ReadFile(fmt.Sprintf("/proc/%d/cmdline", pid))
		if strings.Contains(string(cmd), "/dev/mf79u/") {
			_ = syscall.Kill(pid, syscall.SIGTERM)
		}
	}
	_ = os.Remove("/dev/mf79u/" + name)
}
func setDNS(b []byte) error {
	if _, e := os.Stat("/dev/mf79u/resolv.before"); os.IsNotExist(e) {
		old, _ := os.ReadFile("/tmp/resolv.conf")
		if e = atomicFile("/dev/mf79u/resolv.before", old, 0600); e != nil {
			return e
		}
	}
	if e := atomicFile("/dev/mf79u/resolv.conf", b, 0644); e != nil {
		return e
	}
	return atomicFile("/tmp/resolv.conf", b, 0644)
}
func (a *App) apDHCP() error {
	a.mu.Lock()
	n := a.settings.LAN
	a.mu.Unlock()
	return a.lanApply(n)
}

func (a *App) setNetworkError(e error) { a.mu.Lock(); defer a.mu.Unlock(); a.networkError = e.Error() }

func webAccess() error {
	_ = run("iptables", "-N", "MF79U_WEB")
	if e := run("iptables", "-F", "MF79U_WEB"); e != nil {
		return e
	}
	for _, port := range []string{"80", "18080"} {
		if e := run("iptables", "-A", "MF79U_WEB", "-i", "wan+", "-p", "tcp", "--dport", port, "-j", "REJECT"); e != nil {
			return e
		}
	}

	// SSH is reachable only on the management LAN, irrespective of vendor firewall changes.
	for _, iface := range []string{"bridge0", "wlan0", "wlan0-vxd", "lo"} {
		if e := run("iptables", "-A", "MF79U_WEB", "-i", iface, "-p", "tcp", "--dport", "22", "-j", "ACCEPT"); e != nil {
			return e
		}
	}
	if e := run("iptables", "-A", "MF79U_WEB", "-p", "tcp", "--dport", "22", "-j", "REJECT"); e != nil {
		return e
	}
	_ = run("iptables", "-D", "INPUT", "-j", "MF79U_WEB")
	if e := run("iptables", "-I", "INPUT", "1", "-j", "MF79U_WEB"); e != nil {
		return e
	}
	if _, e := exec.LookPath("ip6tables"); e == nil {
		_ = run("ip6tables", "-N", "MF79U_WEB")
		if e = run("ip6tables", "-F", "MF79U_WEB"); e != nil {
			return e
		}
		for _, port := range []string{"80", "18080"} {
			if e = run("ip6tables", "-A", "MF79U_WEB", "-i", "wan+", "-p", "tcp", "--dport", port, "-j", "DROP"); e != nil {
				return e
			}
		}
		if e = run("ip6tables", "-A", "MF79U_WEB", "-p", "tcp", "--dport", "22", "-j", "DROP"); e != nil {
			return e
		}
		_ = run("ip6tables", "-D", "INPUT", "-j", "MF79U_WEB")
		if e = run("ip6tables", "-I", "INPUT", "1", "-j", "MF79U_WEB"); e != nil {
			return e
		}
	}
	for _, iface := range []string{"bridge0", "wlan0", "wlan0-vxd"} {
		_ = run("iptables", "-t", "nat", "-D", "PREROUTING", "-i", iface, "-p", "tcp", "--dport", "80", "-j", "REDIRECT", "--to-ports", "18080")
		if e := run("iptables", "-t", "nat", "-I", "PREROUTING", "1", "-i", iface, "-p", "tcp", "--dport", "80", "-j", "REDIRECT", "--to-ports", "18080"); e != nil {
			return e
		}
	}
	return nil
}

// USB internet is supplied by a host in the existing management LAN. Keep its
// connected subnet and all cellular bearer routes; own only metric-5 defaults.
func (a *App) applyVoWiFiUplink(v VoWiFi) error {
	const marker = "/dev/mf79u/vowifi-usb-route-owner"
	const ready = "/dev/mf79u/vowifi-usb-ready"
	// Keep an already owned USB uplink live while Wi-Fi or other settings apply.
	if old, e := os.ReadFile(marker); e == nil && v.Uplink == "USB" && strings.TrimSpace(string(old)) == v.Gateway {
		owned := true
		for _, prefix := range []string{"0.0.0.0/1", "128.0.0.0/1"} {
			found := false
			for _, line := range strings.Split(output("ip", "route", "show", prefix), "\n") {
				if strings.Join(strings.Fields(line), " ") == prefix+" via "+v.Gateway+" dev bridge0 metric 5" {
					found = true
				}
			}
			owned = owned && found
		}
		if owned {
			var dns strings.Builder
			for _, ip := range v.DNS {
				dns.WriteString("nameserver " + ip + "\n")
			}
			if e := atomicFile("/tmp/resolv.conf", []byte(dns.String()), 0644); e != nil {
				return e
			}
			return atomicFile(ready, []byte("USB\n"), 0600)
		}
	}
	_ = os.Remove(ready)
	const saved = "/dev/mf79u/vowifi-usb-resolv.before"
	if old, e := os.ReadFile(marker); e == nil {
		gateway := strings.TrimSpace(string(old))
		if net.ParseIP(gateway).To4() != nil {
			for _, prefix := range []string{"0.0.0.0/1", "128.0.0.0/1"} {
				_ = run("ip", "route", "del", prefix, "via", gateway, "dev", "bridge0", "metric", "5")
			}
		}
		_ = os.Remove(marker)
		if dns, e := os.ReadFile(saved); e == nil {
			_ = atomicFile("/tmp/resolv.conf", dns, 0644)
			_ = os.Remove(saved)
		}
	}
	if v.Uplink != "USB" {
		return nil
	}
	if e := ensureUSBLAN(); e != nil {
		return e
	}
	for _, prefix := range []string{"0.0.0.0/1", "128.0.0.0/1"} {
		if strings.Contains(output("ip", "route", "show", prefix), "metric 5 ") || strings.HasSuffix(output("ip", "route", "show", prefix), "metric 5") {
			return errors.New("USB internet route conflicts with an existing route")
		}
	}
	before, e := os.ReadFile("/tmp/resolv.conf")
	if e != nil {
		return e
	}
	if e = atomicFile(saved, before, 0600); e != nil {
		return e
	}
	// Publish the gateway first so a partial failure is also reversible.
	if e = atomicFile(marker, []byte(v.Gateway+"\n"), 0600); e != nil {
		return e
	}
	for _, prefix := range []string{"0.0.0.0/1", "128.0.0.0/1"} {
		if e = run("ip", "route", "add", prefix, "via", v.Gateway, "dev", "bridge0", "metric", "5"); e != nil {
			return e
		}
	}
	var dns strings.Builder
	for _, ip := range v.DNS {
		dns.WriteString("nameserver " + ip + "\n")
	}
	if e := atomicFile("/tmp/resolv.conf", []byte(dns.String()), 0644); e != nil {
		return e
	}
	return atomicFile(ready, []byte("USB\n"), 0600)
}
