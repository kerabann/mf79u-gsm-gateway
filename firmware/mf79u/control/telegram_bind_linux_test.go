//go:build linux

package main

import (
	"crypto/tls"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestTelegramLinuxInterfaceBindingFailsClosed(t *testing.T) {
	hits := 0
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { hits++; io.WriteString(w, `{"ok":true}`) }))
	defer server.Close()
	client := telegramClient("lo")
	defer client.CloseIdleConnections()
	trust := server.Client().Transport.(*http.Transport).TLSClientConfig.Clone()
	trust.MinVersion = tls.VersionTLS12
	client.Transport.(*http.Transport).TLSClientConfig = trust
	if _, e := telegramRequest(client, server.URL, telegramFixture(), smsSIPItem{Number: "Fixture", Text: "Hello"}); e != nil || hits != 1 {
		t.Fatal("bound loopback TLS request failed", e)
	}
	other := telegramClient("missing0")
	defer other.CloseIdleConnections()
	other.Transport.(*http.Transport).TLSClientConfig = trust
	if _, e := telegramRequest(other, server.URL, telegramFixture(), smsSIPItem{Number: "Fixture", Text: "Hello"}); e == nil || hits != 1 {
		t.Fatal("missing interface fell back")
	}
}
