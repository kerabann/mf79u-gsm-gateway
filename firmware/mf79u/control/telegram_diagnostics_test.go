package main

import (
	"context"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"errors"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"syscall"
	"testing"
	"time"
)

func TestTelegramOfficialRootAndStrictVerification(t *testing.T) {
	block, rest := pem.Decode(telegramPublicRoot)
	if block == nil || len(strings.TrimSpace(string(rest))) != 0 {
		t.Fatal("expected one public CA certificate")
	}
	cert, e := x509.ParseCertificate(block.Bytes)
	if e != nil || !cert.IsCA || cert.Subject.CommonName != "Go Daddy Root Certificate Authority - G2" || cert.CheckSignatureFrom(cert) != nil {
		t.Fatal("invalid public trust anchor")
	}
	sum := sha256.Sum256(cert.Raw)
	if hex.EncodeToString(sum[:]) != "45140b3247eb9cc8c5b4f0d7b53091f73292089e6e5a63e2749dd3aca9198eda" {
		t.Fatal("official DER root fingerprint changed")
	}
	if _, e := cert.Verify(x509.VerifyOptions{Roots: telegramRootPool(), CurrentTime: time.Date(2026, 10, 11, 0, 0, 0, 0, time.UTC)}); e != nil {
		t.Fatal("bundled root not trusted")
	}
	client := telegramClient("bridge0")
	defer client.CloseIdleConnections()
	c := client.Transport.(*http.Transport).TLSClientConfig
	if c.InsecureSkipVerify || c.MinVersion == 0 || c.RootCAs == nil {
		t.Fatal("TLS verification disabled")
	}
}

func TestTelegramDiagnosticCategoriesNeverExposePrivateError(t *testing.T) {
	for _, tc := range []struct {
		err      error
		category string
	}{
		{&net.DNSError{Err: "private DNS details", Name: "private", IsTimeout: true}, "dns_failed"},
		{x509.UnknownAuthorityError{}, "tls_untrusted_root"},
		{x509.CertificateInvalidError{}, "tls_invalid_certificate"},
		{x509.HostnameError{}, "tls_hostname_mismatch"},
		{syscall.ENETUNREACH, "network_unreachable"},
		{syscall.EACCES, "socket_permission_denied"},
		{syscall.ENODEV, "interface_unavailable"},
		{context.DeadlineExceeded, "request_timeout"},
		{errors.New("private token or body"), "https_failed"},
	} {
		e := &url.Error{Op: "Get", URL: "https://private-token/getChat?chat_id=private", Err: tc.err}
		if telegramErrorCategory(e) != tc.category {
			t.Fatal("wrong sanitized diagnostic category")
		}
	}
}

func TestTelegramDiagnosticReadOnlyResponseAllowlist(t *testing.T) {
	status := 200
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" || strings.Contains(r.URL.Path, "sendMessage") {
			t.Fatal("diagnostic submitted a message")
		}
		w.WriteHeader(status)
		if status == 200 {
			io.WriteString(w, `{"ok":true,"result":{"id":123,"username":"private","first_name":"private"}}`)
		} else {
			io.WriteString(w, `{"ok":false,"error_code":400,"description":"private details"}`)
		}
	}))
	defer server.Close()
	for _, code := range []int{200, 400} {
		status = code
		r, ok := telegramDiagnosticRequest(server.Client(), server.URL+"/getMe")
		if ok != (code == 200) || r["httpStatus"] != code {
			t.Fatal("diagnostic response")
		}
		b, _ := json.Marshal(r)
		if strings.Contains(string(b), "private") {
			t.Fatal("private bot/chat response leaked")
		}
	}
	client := telegramClient("unavailable0")
	defer client.CloseIdleConnections()
	r, ok := telegramDiagnosticRequest(client, server.URL+"/private-token/getChat?chat_id=private")
	b, _ := json.Marshal(r)
	if ok || strings.Contains(string(b), "private") {
		t.Fatal("private token URL leaked")
	}
}
