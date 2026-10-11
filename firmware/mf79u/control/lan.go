package main

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
)

func ipNumber(ip net.IP) uint32 { return binary.BigEndian.Uint32(ip.To4()) }
func numberIP(n uint32) string {
	b := make([]byte, 4)
	binary.BigEndian.PutUint32(b, n)
	return net.IP(b).String()
}
func migrateLAN(n *Network) error {
	if n.Subnet == "" {
		ip, network, e := net.ParseCIDR(n.Address)
		if e != nil || ip.To4() == nil {
			return errors.New("Invalid management address")
		}
		prefix, _ := network.Mask.Size()
		if prefix < 8 || prefix > 30 {
			return errors.New("Subnet prefix must be /8–/30")
		}
		n.Subnet = network.String()
		n.Gateway = ip.String()
		first, last := ipNumber(network.IP)+1, ipNumber(network.IP)|^binary.BigEndian.Uint32(network.Mask)
		// Keep the previous /24 pool, choose the larger contiguous side for other prefixes.
		gw := ipNumber(ip)
		if gw-first > last-gw-1 {
			n.PoolStart = numberIP(first)
			n.PoolEnd = numberIP(gw - 1)
		} else {
			n.PoolStart = numberIP(gw + 1)
			n.PoolEnd = numberIP(last - 1)
			if prefix == 24 && gw == first {
				n.PoolEnd = numberIP(last - 2)
			}
		}
	}
	_, network, e := net.ParseCIDR(n.Subnet)
	if e != nil || network.IP.To4() == nil {
		return errors.New("Invalid IPv4 subnet")
	}
	prefix, _ := network.Mask.Size()
	n.Mode = "STATIC"
	n.Address = fmt.Sprintf("%s/%d", n.Gateway, prefix)
	if len(n.DNS) == 0 {
		n.DNS = []string{"1.1.1.1", "8.8.8.8"}
	}
	if n.Routes == nil {
		n.Routes = []DHCPRoute{}
	}
	for i := range n.Routes {
		if !strings.Contains(n.Routes[i].Destination, "/") {
			n.Routes[i].Destination += "/32"
		}
	}
	return nil
}
func validateLAN(n Network) error {
	// Legacy fixtures/settings are migrated on load and PUT.
	if n.Subnet == "" {
		return nil
	}
	ip, network, e := net.ParseCIDR(n.Subnet)
	if e != nil || ip.To4() == nil {
		return errors.New("Enter an IPv4 subnet, for example 192.168.0.0/24")
	}
	prefix, _ := network.Mask.Size()
	if prefix < 8 || prefix > 30 || !ip.Equal(network.IP) {
		return errors.New("Use a subnet network address with prefix /8–/30")
	}
	first := ipNumber(network.IP)
	last := first | ^binary.BigEndian.Uint32(network.Mask)
	host := func(s string) bool {
		p := net.ParseIP(s).To4()
		return p != nil && network.Contains(p) && ipNumber(p) > first && ipNumber(p) < last
	}
	if !host(n.Gateway) || !host(n.PoolStart) || !host(n.PoolEnd) {
		return errors.New("Gateway and pool must be usable addresses inside the subnet")
	}
	low, high, gw := ipNumber(net.ParseIP(n.PoolStart)), ipNumber(net.ParseIP(n.PoolEnd)), ipNumber(net.ParseIP(n.Gateway))
	if low <= 0xc0a80001 && high >= 0xc0a80001 {
		return errors.New("DHCP pool must exclude the recovery address 192.168.0.1")
	}
	if low > high || gw >= low && gw <= high {
		return errors.New("DHCP pool must be ordered and exclude the modem gateway")
	}
	if n.Address != fmt.Sprintf("%s/%d", n.Gateway, prefix) {
		return errors.New("Management address must match the subnet and gateway")
	}
	if len(n.DNS) < 1 || len(n.DNS) > 3 {
		return errors.New("Enter 1–3 IPv4 DNS servers")
	}
	for _, s := range n.DNS {
		p := net.ParseIP(s)
		if p.To4() == nil || p.IsUnspecified() || p.IsMulticast() {
			return errors.New("Invalid DNS server")
		}
	}
	if len(n.Routes) > 20 {
		return errors.New("Use up to 20 DHCP routes")
	}
	seen := map[string]bool{}
	for _, r := range n.Routes {
		p, d, e := net.ParseCIDR(r.Destination)
		if e != nil || p.To4() == nil {
			return errors.New("Route destination must be IPv4 or CIDR")
		}
		width, _ := d.Mask.Size()
		if width == 0 || !p.Equal(d.IP) || !host(r.Gateway) || seen[d.String()] {
			return errors.New("Routes require unique network destinations and a gateway in the LAN subnet; default route uses IP gateway")
		}
		seen[d.String()] = true
	}
	return nil
}
func classlessRoutes(n Network) string {
	// RFC3442: when option121 exists, clients ignore option3. Include default.
	data := append([]byte{0}, net.ParseIP(n.Gateway).To4()...)
	for _, r := range n.Routes {
		_, d, _ := net.ParseCIDR(r.Destination)
		width, _ := d.Mask.Size()
		data = append(data, byte(width))
		data = append(data, d.IP.To4()[:(width+7)/8]...)
		data = append(data, net.ParseIP(r.Gateway).To4()...)
	}
	var parts []string
	for _, b := range data {
		parts = append(parts, fmt.Sprintf("%02x", b))
	}
	return strings.Join(parts, ":")
}
func managedDHCPOption(line string) bool {
	if !strings.HasPrefix(line, "dhcp-option=") && !strings.HasPrefix(line, "dhcp-option-force=") {
		return false
	}
	_, value, _ := strings.Cut(line, "=")
	for _, part := range strings.Split(value, ",") {
		if strings.HasPrefix(part, "tag:") {
			continue
		}
		return part == "3" || part == "6" || part == "121" || part == "249" || part == "option:router" || part == "option:dns-server" || part == "option:classless-static-route"
	}
	return false
}
func dnsmasqConfig(current string, n Network) []byte {
	var keep []string
	for _, line := range strings.Split(strings.ReplaceAll(current, "\r", ""), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "# MF79U") || strings.HasPrefix(line, "dhcp-range=") || managedDHCPOption(line) || strings.HasPrefix(line, "address=/ufi.ztedevice.com/") || strings.HasPrefix(line, "interface=") {
			continue
		}
		keep = append(keep, line)
	}
	if !strings.Contains(strings.Join(keep, "\n"), "dhcp-leasefile=") {
		keep = append(keep, "dhcp-leasefile=/etc_rw_mbb/ztembb/configs/dnsmasq.leases")
	}
	_, subnet, _ := net.ParseCIDR(n.Subnet)
	keep = append(keep, "# MF79U shared USB/Wi-Fi DHCP", "interface=bridge0", "address=/ufi.ztedevice.com/"+n.Gateway, "dhcp-range="+n.PoolStart+","+n.PoolEnd+","+net.IP(subnet.Mask).String()+",24h", "dhcp-option=3,"+n.Gateway, "dhcp-option=6,"+strings.Join(n.DNS, ","))
	if len(n.Routes) > 0 {
		route := classlessRoutes(n)
		keep = append(keep, "dhcp-option=121,"+route, "dhcp-option=249,"+route)
	}
	return []byte(strings.Join(keep, "\n") + "\n")
}
func lanDNSProcesses() []int {
	var pids []int
	entries, _ := os.ReadDir("/proc")
	for _, e := range entries {
		pid, err := strconv.Atoi(e.Name())
		if err != nil || pid < 2 {
			continue
		}
		exe, _ := os.Readlink("/proc/" + e.Name() + "/exe")
		if filepath.Base(exe) != "dnsmasq" {
			continue
		}
		b, _ := os.ReadFile("/proc/" + e.Name() + "/cmdline")
		args := strings.Split(string(b), "\x00")
		for i, s := range args {
			if s == "--conf-file=/tmp/dnsmasq.conf" || s == "-C" && i+1 < len(args) && args[i+1] == "/tmp/dnsmasq.conf" {
				pids = append(pids, pid)
				break
			}
		}
	}
	return pids
}
func (a *App) lanDHCP(n Network) error {
	if e := migrateLAN(&n); e != nil {
		return e
	}
	if e := validateLAN(n); e != nil {
		return e
	}
	const path = "/tmp/dnsmasq.conf"
	current, e := os.ReadFile(path)
	if e != nil {
		return errors.New("Vendor LAN DHCP configuration is unavailable")
	}
	wanted := dnsmasqConfig(string(current), n)
	pids := lanDNSProcesses()
	if bytes.Equal(current, wanted) && len(pids) == 1 {
		return nil
	}
	if _, e := os.Stat(filepath.Join(a.dir, "dnsmasq.vendor-before-network.conf")); os.IsNotExist(e) {
		if e = atomicFile(filepath.Join(a.dir, "dnsmasq.vendor-before-network.conf"), current, 0600); e != nil {
			return e
		}
	}
	stage := "/dev/mf79u/lan-dhcp.check.conf"
	if e := atomicFile(stage, wanted, 0600); e != nil {
		return e
	}
	defer os.Remove(stage)
	if e := run("dnsmasq", "--test", "--conf-file="+stage); e != nil {
		return errors.New("DHCP configuration syntax check failed")
	}
	if e := atomicFile(path, wanted, 0600); e != nil {
		return e
	}
	// Only the inventory tied to the vendor LAN config may be restarted.
	for _, pid := range pids {
		for _, live := range lanDNSProcesses() {
			if pid == live {
				if e := syscall.Kill(pid, syscall.SIGTERM); e != nil {
					return e
				}
			}
		}
	}
	deadline := time.Now().Add(3 * time.Second)
	for len(lanDNSProcesses()) > 0 && time.Now().Before(deadline) {
		time.Sleep(50 * time.Millisecond)
	}
	if len(lanDNSProcesses()) > 0 {
		return errors.New("LAN DHCP service did not stop")
	}
	if e := run("dnsmasq", "-u", "admin", "-c", "300", "-C", path, "-z"); e != nil {
		return errors.New("LAN DHCP service could not start")
	}
	if len(lanDNSProcesses()) != 1 {
		return errors.New("LAN DHCP service ownership could not be verified")
	}
	return nil
}
func (a *App) maintainLAN() {
	for range time.NewTicker(10 * time.Second).C {
		a.netmu.Lock()
		a.mu.Lock()
		n := a.applied.LAN
		if a.pending != "" && a.networkReady {
			n = a.settings.LAN
		}
		a.mu.Unlock()
		if e := a.lanApply(n); e != nil {
			a.setNetworkError(fmt.Errorf("LAN DHCP: %s", e))
		} else {
			a.mu.Lock()
			if strings.HasPrefix(a.networkError, "LAN DHCP: ") {
				a.networkError = ""
			}
			a.mu.Unlock()
		}
		a.netmu.Unlock()
	}
}
