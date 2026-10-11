package main

import (
	"context"
	"crypto/x509"
	"encoding/json"
	"errors"
	"io"
	"net"
	"net/http"
	"net/url"
	"syscall"
	"time"
)

// Error URLs/response bodies include private token, chat and bot details.
// Return only fixed categories and numeric Bot API errors, never raw strings.
func telegramErrorCategory(e error) string {
	var dns *net.DNSError
	var authority x509.UnknownAuthorityError
	var certificate x509.CertificateInvalidError
	var hostname x509.HostnameError
	switch {
	case errors.As(e, &dns):
		return "dns_failed"
	case errors.As(e, &authority):
		return "tls_untrusted_root"
	case errors.As(e, &certificate):
		return "tls_invalid_certificate"
	case errors.As(e, &hostname):
		return "tls_hostname_mismatch"
	case errors.Is(e, syscall.ENETUNREACH):
		return "network_unreachable"
	case errors.Is(e, syscall.EHOSTUNREACH):
		return "host_unreachable"
	case errors.Is(e, syscall.EPERM), errors.Is(e, syscall.EACCES):
		return "socket_permission_denied"
	case errors.Is(e, syscall.ENODEV):
		return "interface_unavailable"
	case errors.Is(e, context.DeadlineExceeded):
		return "request_timeout"
	default:
		return "https_failed"
	}
}

func telegramDiagnosticRequest(client *http.Client, endpoint string) (map[string]any, bool) {
	r, e := client.Get(endpoint)
	if e != nil {
		return map[string]any{"ok": false, "error": telegramErrorCategory(e)}, false
	}
	defer r.Body.Close()
	var reply struct {
		OK        bool `json:"ok"`
		ErrorCode int  `json:"error_code"`
	}
	if e := json.NewDecoder(io.LimitReader(r.Body, 65536)).Decode(&reply); e != nil {
		return map[string]any{"ok": false, "httpStatus": r.StatusCode, "error": "invalid_response"}, false
	}
	ok := r.StatusCode == 200 && reply.OK
	return map[string]any{"ok": ok, "httpStatus": r.StatusCode, "apiErrorCode": reply.ErrorCode}, ok
}

func telegramDiagnostics(dir string) map[string]any {
	report := map[string]any{"readOnly": true, "messageSubmitted": false}
	s, e := readSettings(dir)
	if e != nil {
		report["error"] = "settings_unavailable"
		return report
	}
	c := s.Webhooks.TelegramSMS
	if c.BotToken == "" || c.ChatID == "" || c.Interface == "" {
		report["error"] = "telegram_unconfigured"
		return report
	}
	iface, e := interfaceByName(c.Interface)
	if e != nil || iface.Flags&net.FlagUp == 0 {
		report["error"] = "interface_unavailable"
		return report
	}
	report["interface"] = c.Interface
	ctx, cancel := context.WithTimeout(context.Background(), 12*time.Second)
	defer cancel()
	dialer := telegramDialer(c.Interface)
	ips, e := dialer.Resolver.LookupIPAddr(ctx, "api.telegram.org")
	if e != nil {
		report["dns"] = telegramErrorCategory(e)
		return report
	}
	report["dns"] = "ok"
	report["resolvedAddressCount"] = len(ips)
	client := telegramClient(c.Interface)
	defer client.CloseIdleConnections()
	base := "https://api.telegram.org/bot" + c.BotToken
	bot, ok := telegramDiagnosticRequest(client, base+"/getMe")
	report["bot"] = bot
	if !ok {
		return report
	}
	chat, _ := telegramDiagnosticRequest(client, base+"/getChat?"+url.Values{"chat_id": {c.ChatID}}.Encode())
	report["chat"] = chat
	return report
}
