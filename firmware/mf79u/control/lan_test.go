package main

import (
	"strings"
	"testing"
)

func testLAN() Network { n := defaults().LAN; _ = migrateLAN(&n); return n }
func TestLANMigrationValidation(t *testing.T) {
	n := testLAN()
	if n.Subnet != "192.168.0.0/24" || n.PoolStart != "192.168.0.2" || n.PoolEnd != "192.168.0.253" {
		t.Fatal("legacy migration failed")
	}
	n.PoolEnd = "192.168.0.253"
	if e := validateLAN(n); e != nil {
		t.Fatal(e)
	}
	for _, mutate := range []func(*Network){func(n *Network) { n.Subnet = "192.168.0.1/24" }, func(n *Network) { n.PoolStart = "192.168.1.2" }, func(n *Network) { n.PoolStart = "192.168.0.254" }, func(n *Network) { n.Gateway = "192.168.0.10" }, func(n *Network) { n.DNS = []string{"invalid"} }, func(n *Network) { n.Routes = []DHCPRoute{{Destination: "0.0.0.0/0", Gateway: "192.168.0.10"}} }, func(n *Network) { n.Routes = []DHCPRoute{{Destination: "1.2.3.4/32", Gateway: "192.168.1.10"}} }} {
		bad := n
		mutate(&bad)
		if validateLAN(bad) == nil {
			t.Fatal("invalid LAN accepted")
		}
	}
	old := Network{Mode: "STATIC", Address: "192.168.7.1/24"}
	if migrateLAN(&old) != nil || old.Gateway != "192.168.7.1" || old.Subnet != "192.168.7.0/24" {
		t.Fatal("legacy address lost")
	}
}
func TestClasslessRoutesDefaultAndPartialPrefix(t *testing.T) {
	n := testLAN()
	n.Routes = []DHCPRoute{{Destination: "1.2.3.4/32", Gateway: "192.168.0.10"}, {Destination: "10.128.0.0/9", Gateway: "192.168.0.11"}}
	if classlessRoutes(n) != "00:c0:a8:00:01:20:01:02:03:04:c0:a8:00:0a:09:0a:80:c0:a8:00:0b" {
		t.Fatal("RFC3442 encoding failed")
	}
	cfg := string(dnsmasqConfig("interface=bridge0\ndhcp-range=old\ndhcp-option=3,old\ndhcp-option=15,example.org\nserver=10.0.0.1\n", n))
	for _, s := range []string{"dhcp-option=3,192.168.0.1", "dhcp-option=6,1.1.1.1,8.8.8.8", "dhcp-option=121,00:c0", "dhcp-option=249,00:c0", "server=10.0.0.1", "dhcp-option=15,example.org"} {
		if !strings.Contains(cfg, s) {
			t.Fatal("DHCP options lost")
		}
	}
	if strings.Contains(cfg, "old") || string(dnsmasqConfig(cfg, n)) != cfg {
		t.Fatal("DHCP configuration not idempotent")
	}
	n.Routes = nil
	if strings.Contains(string(dnsmasqConfig(cfg, n)), "dhcp-option=121") {
		t.Fatal("removed routes persisted")
	}
}
