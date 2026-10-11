package main

import (
	"strings"
	"testing"
)

func TestVendorFirewallRebuildDetected(t *testing.T) {
	filter := "-A INPUT -j MF79U_WEB\n-A FORWARD -j MF79U_SHARE\n-A OUTPUT -j MF79U_DATA\n" +
		"-A MF79U_DATA -o wan5 -j RETURN\n-A MF79U_DATA -o wan+ -j REJECT --reject-with icmp-port-unreachable\n" +
		"-A MF79U_WEB -i wan+ -p tcp -m tcp --dport 80 -j REJECT --reject-with icmp-port-unreachable\n" +
		"-A MF79U_WEB -i wan+ -p tcp -m tcp --dport 18080 -j REJECT --reject-with icmp-port-unreachable\n" +
		"-A MF79U_SHARE -o wan+ -j REJECT --reject-with icmp-port-unreachable\n" +
		"-A MF79U_SHARE -i wan+ -j REJECT --reject-with icmp-port-unreachable\n"
	filter += "-A MF79U_WEB -p tcp -m tcp --dport 22 -j REJECT --reject-with icmp-port-unreachable\n"
	for _, iface := range []string{"bridge0", "wlan0", "wlan0-vxd", "lo"} {
		filter += "-A MF79U_WEB -i " + iface + " -p tcp -m tcp --dport 22 -j ACCEPT\n"
	}
	filter6 := strings.ReplaceAll(filter, "REJECT --reject-with icmp-port-unreachable", "DROP")
	nat := ""
	for _, iface := range []string{"bridge0", "wlan0", "wlan0-vxd"} {
		nat += "-A PREROUTING -i " + iface + " -p tcp -m tcp --dport 80 -j REDIRECT --to-ports 18080 \n"
	}
	if !firewallIntact(filter, nat, filter6, false) {
		t.Fatal("complete native rules were rejected")
	}
	if firewallIntact(strings.ReplaceAll(filter, "--dport 18080", "--dport 12345"), nat, filter6, false) {
		t.Fatal("vendor-cleared web protection was not detected")
	}
	if firewallIntact(filter, strings.ReplaceAll(nat, "bridge0", "other0"), filter6, false) {
		t.Fatal("vendor-removed USB redirect was not detected")
	}
	if firewallIntact("-A INPUT -j vendor_accept\n"+filter, nat, filter6, false) {
		t.Fatal("a vendor rule preceding our access restriction was not detected")
	}
	if firewallIntact(filter, nat, filter6, true) {
		t.Fatal("sharing enabled while still blocked was not detected")
	}
	if firewallIntact(strings.ReplaceAll(filter, "-o wan5 -j RETURN", "-o wan1 -j RETURN"), nat, filter6, false) {
		t.Fatal("ordinary cellular internet incorrectly exempted from OUTPUT restriction")
	}
	if firewallIntact(strings.ReplaceAll(filter, "-A OUTPUT -j MF79U_DATA", "-A OUTPUT -j vendor_accept\n-A OUTPUT -j MF79U_DATA"), nat, filter6, false) {
		t.Fatal("OUTPUT restriction bypassed by an earlier vendor rule")
	}
	withoutShare := func(s string) string {
		lines := []string{}
		for _, line := range strings.Split(s, "\n") {
			if !strings.HasPrefix(line, "-A MF79U_SHARE ") && !strings.HasPrefix(line, "-A MF79U_DATA ") {
				lines = append(lines, line)
			}
		}
		return strings.Join(lines, "\n")
	}
	if !firewallIntact(withoutShare(filter), nat, withoutShare(filter6), true) {
		t.Fatal("enabled sharing profile was rejected")
	}
}
