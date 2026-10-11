package main

import "testing"

func TestVoWiFiUSBGatewayValidation(t *testing.T) {
	lan := Network{Address: "192.168.0.1/24"}
	for _, gw := range []string{"192.168.0.1", "192.168.0.0", "192.168.0.255", "192.168.50.1", "127.0.0.1", "bad"} {
		if validateVoWiFi(VoWiFi{Uplink: "USB", Gateway: gw, DNS: []string{"1.1.1.1"}}, lan) == nil {
			t.Fatalf("accepted invalid gateway %s", gw)
		}
	}
	if e := validateVoWiFi(VoWiFi{Uplink: "USB", Gateway: "192.168.0.169", DNS: []string{"1.1.1.1"}}, lan); e != nil {
		t.Fatal(e)
	}
	if validateVoWiFi(VoWiFi{Uplink: "USB", Gateway: "192.168.0.169"}, lan) == nil {
		t.Fatal("accepted missing DNS")
	}
	if validateVoWiFi(VoWiFi{}, lan) != nil {
		t.Fatal("legacy Wi-Fi configuration rejected")
	}
}
