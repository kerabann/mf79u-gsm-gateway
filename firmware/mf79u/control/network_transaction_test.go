package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"
)

func pendingFixture(t *testing.T) (*App, Settings) {
	t.Helper()
	a := fixtureApp(nil)
	a.dir = t.TempDir()
	old := defaults()
	a.applied = old
	a.rollback = &old
	a.pending = "fixture-network"
	a.settings = old
	a.settings.LAN.DNS = []string{"8.8.8.8"}
	return a, old
}

func TestNetworkConfirmationLifecycle(t *testing.T) {
	a, _ := pendingFixture(t)
	body := `{"token":"fixture-network"}`
	if w := adminRequest(a, "POST", "/api/network/confirm", body, true, true); w.Code != 409 || a.pending == "" {
		t.Fatal("unfinished network apply was confirmed")
	}
	a.networkReady = true
	a.networkRollingBack = true
	if w := adminRequest(a, "POST", "/api/network/confirm", body, true, true); w.Code != 409 {
		t.Fatal("rollback was confirmed")
	}
	a.networkRollingBack = false
	if w := adminRequest(a, "POST", "/api/network/confirm", `{"token":"stale"}`, true, true); w.Code != 409 {
		t.Fatal("stale transaction was accepted")
	}
	if w := adminRequest(a, "POST", "/api/network/confirm", body, true, true); w.Code != 200 || a.pending != "" || !reflect.DeepEqual(a.applied, a.settings) {
		t.Fatal("ready profile was not committed")
	}
}

func TestNetworkRollbackRestoresProfileWithoutFalseError(t *testing.T) {
	for _, message := range []string{"Network changes rolled back.", "Network changes were not confirmed in time and were rolled back."} {
		a, old := pendingFixture(t)
		a.settings.SIP.Role = "DISABLED"
		a.rollbackNetwork("fixture-network", message)
		if a.pending != "" || a.networkRollingBack || a.networkReady || a.networkError != "" || a.networkNotice != message {
			t.Fatal("successful rollback left a pending operation or false error")
		}
		var saved Settings
		b, e := os.ReadFile(filepath.Join(a.dir, "settings.json"))
		if e != nil || json.Unmarshal(b, &saved) != nil || !reflect.DeepEqual(saved.LAN, old.LAN) || saved.SIP.Role != "DISABLED" || !reflect.DeepEqual(a.applied, a.settings) {
			t.Fatal("rollback lost confirmed network or separate SIP settings")
		}
	}
}

func TestNetworkRollbackFailureIsVisible(t *testing.T) {
	a, _ := pendingFixture(t)
	a.networkError = "Wi-Fi connection failed."
	a.rollbackNetwork("fixture-network", "")
	if a.networkError != "Wi-Fi connection failed. Network changes rolled back; USB management is still available." {
		t.Fatal("connection failure was hidden or malformed")
	}
	a, _ = pendingFixture(t)
	blocked := filepath.Join(a.dir, "regular-file")
	if e := os.WriteFile(blocked, []byte("fixture"), 0600); e != nil {
		t.Fatal(e)
	}
	a.dir = filepath.Join(blocked, "directory")
	a.rollbackNetwork("fixture-network", "Network changes rolled back.")
	if a.networkError == "" {
		t.Fatal("failed restoration was reported as success")
	}
}

func TestDelayedNetworkApplyCannotUndoEarlyRollback(t *testing.T) {
	a, old := pendingFixture(t)
	abandoned := a.settings
	a.rollbackNetwork("fixture-network", "Network changes rolled back.")
	// Execute the real delayed worker after the cancellation has completed.
	// It must return before touching any hardware or changing the notice/profile.
	a.applyNetworkChange("fixture-network", abandoned, old, time.Now())
	if a.networkReady || a.networkError != "" || a.pending != "" || !reflect.DeepEqual(a.settings, old) {
		t.Fatal("delayed worker applied an abandoned network transaction")
	}
	a.pending = "new-network"
	a.rollback = &old
	a.applyNetworkChange("fixture-network", abandoned, old, time.Now())
	if a.networkReady || a.networkError != "" || a.pending != "new-network" || a.networkNotice != "Network changes rolled back." {
		t.Fatal("stale worker modified the replacement transaction")
	}
}

func TestNetworkSIPReloadOnlyForSIPChanges(t *testing.T) {
	old := defaults()
	old.SIP.Role, old.SIP.Bind = "SERVER", "192.168.0.1"
	for _, change := range []func(*Settings){
		func(s *Settings) { s.LAN.DNS = []string{"8.8.8.8"} },
		func(s *Settings) { s.WiFi.Enabled = !s.WiFi.Enabled },
		func(s *Settings) { s.VoiceMode = "CS" },
		func(s *Settings) { s.VoWiFi.Uplink = "USB" },
	} {
		next := old
		change(&next)
		if sipNeedsReload(next, old) {
			t.Fatal("unrelated setting would discard a registered SIP client")
		}
	}
	for _, change := range []func(*Settings){
		func(s *Settings) { s.LAN.Address = "192.168.0.254/24" },
		func(s *Settings) { s.SIP.ExtensionPassword = "fixture-new-client" },
		func(s *Settings) { s.SIP.LocalPort++ },
		func(s *Settings) { s.SIP.Role = "DISABLED" },
	} {
		next := old
		change(&next)
		if !sipNeedsReload(next, old) {
			t.Fatal("changed SIP listener/account was not reloaded")
		}
	}
	a, _ := pendingFixture(t)
	a.settings.SIP.Role, a.settings.SIP.Bind = "SERVER", "192.168.0.254"
	a.settings.LAN.Address = "192.168.0.254/24"
	a.rollbackNetwork("fixture-network", "Network changes rolled back.")
	if a.settings.SIP.Bind != "192.168.0.1" {
		t.Fatal("rollback retained the abandoned registrar address")
	}
}
