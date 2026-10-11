package main

import (
	"os"
	"testing"
)

func TestParseB03InterfaceAddresses(t *testing.T) {
	text := "17: bridge0: <UP> mtu 1500\n    link/ether 00:01:02:03:04:05\n    inet 192.168.0.1/24 brd 192.168.0.255\n    inet6 fe80::1/64 scope link\n    inet invalid\n"
	addresses := parseInterfaceAddresses(text)
	if len(addresses) != 2 || addresses[0].String() != "192.168.0.1/24" || addresses[1].String() != "fe80::1/64" {
		t.Fatalf("Unexpected addresses: %v", addresses)
	}
}

func TestB03LiveInterfaceRead(t *testing.T) {
	if os.Getenv("MF79U_LIVE_NETWORK_CHECK") != "1" {
		t.Skip("physical device only")
	}
	iface, e := interfaceByName("bridge0")
	if e != nil {
		t.Fatal(e)
	}
	addresses, e := interfaceAddresses(iface)
	if e != nil || len(addresses) == 0 {
		t.Fatalf("Interface addresses unavailable: %v", e)
	}
	if e := ensureAddress("bridge0", addresses[0].String()); e != nil {
		t.Fatal(e)
	}
	// Read only: do not apply addresses, DHCP settings or factory credentials.
	t.Logf("Management interface read succeeded: %d addresses", len(addresses))
}
