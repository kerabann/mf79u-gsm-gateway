package main

import (
	"encoding/hex"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func testIMSStore(t *testing.T) *imsSMSStore {
	t.Helper()
	dir := t.TempDir()
	spool := filepath.Join(dir, "spool")
	if e := os.Mkdir(spool, 0700); e != nil {
		t.Fatal(e)
	}
	return &imsSMSStore{path: filepath.Join(dir, "state.json"), spool: spool, socket: filepath.Join(dir, "ims.sock")}
}
func TestIMSSubmitGSM7Octets(t *testing.T) {
	p, e := smsSubmitPDUs("12345", "hello")
	if e != nil || len(p) != 1 || p[0] != "00010005812143F5000005E8329BFD06" {
		t.Fatalf("GSM7: %v %v", p, e)
	}
	p, e = smsSubmitPDUs("+12345", "Привет")
	if e != nil || p[0] != "00010005912143F500080C041F04400438043204350442" {
		t.Fatal("UCS2", e)
	}
	for _, text := range []string{"", string([]byte{255}), "x\x00", strings.Repeat("x", 671)} {
		if _, e := smsSubmitPDUs("12345", text); e == nil {
			t.Fatal("invalid text accepted")
		}
	}
}
func TestIMSPDUReceiveAndReject(t *testing.T) {
	p, e := smsDecodePDU("000405912143F500006201112143650005E8329BFD06")
	if e != nil || p.Number != "+12345" || p.Text != "hello" || p.Date != "2026-10-11T12:34:56Z" {
		t.Fatalf("DELIVER %+v %v", p, e)
	}
	p, e = smsDecodePDU("000405912143F50008620111214365000C041F04400438043204350442")
	if e != nil || p.Text != "Привет" {
		t.Fatal(e)
	}
	for _, pdu := range []string{"", "XX", "0000", "000405912143F5000062011121436500FF00", "000405912143F50008620111214365000104"} {
		if _, e := smsDecodePDU(pdu); e == nil {
			t.Fatal("malformed PDU accepted")
		}
	}
}
func TestIMSLongMessagesBoundaries(t *testing.T) {
	for _, text := range []string{strings.Repeat("x", 670), strings.Repeat("^", 335), strings.Repeat("Ж", 670), strings.Repeat("Ж", 66) + "🌍" + strings.Repeat("🌍", 66)} {
		pdus, e := smsSubmitPDUs("12345", text)
		if e != nil || len(pdus) < 2 {
			t.Fatal(e)
		}
		var joined strings.Builder
		for i, pdu := range pdus {
			p, _ := hex.DecodeString(pdu)
			if p[1]&0x40 == 0 {
				t.Fatal("UDHI")
			}
			n := int(p[3])
			pos := 5 + (n+1)/2
			dcs, udl, ud := p[pos+1], int(p[pos+2]), p[pos+3:]
			if len(ud) > 140 || ud[0] != 5 || int(ud[4]) != len(pdus) || int(ud[5]) != i+1 {
				t.Fatal("concat envelope")
			}
			if dcs == 0 {
				value, e := gsmDecode(ud, 49, udl-7)
				if e != nil {
					t.Fatal(e)
				}
				joined.WriteString(value)
			} else {
				units := ud[6:]
				if len(units)%2 != 0 || len(units) < 2 {
					t.Fatal("UCS2 length")
				}
				last := int(units[len(units)-2])<<8 | int(units[len(units)-1])
				first := int(units[0])<<8 | int(units[1])
				if first >= 0xdc00 && first <= 0xdfff || last >= 0xd800 && last <= 0xdbff {
					t.Fatal("split surrogate")
				}
				joined.WriteString(decodeSMS(strings.ToUpper(hex.EncodeToString(units))))
			}
		}
		if joined.String() != text {
			t.Fatal("multipart altered text")
		}
	}
}
func TestIMSIncomingDurabilityDedupeAndMultipart(t *testing.T) {
	s := testIMSStore(t)
	p, _ := smsDecodePDU("000405912143F500006201112143650005E8329BFD06")
	if s.accept(p) != nil || s.accept(p) != nil || len(s.messages()) != 1 {
		t.Fatal("duplicate receive")
	}
	copy := testIMSStore(t)
	copy.path = s.path
	if copy.load() != nil || len(copy.messages()) != 1 {
		t.Fatal("durability")
	}
	first, e := smsDecodePDU("004405912143F5000862011121436500080500037A0201041F")
	if e != nil {
		t.Fatal(e)
	}
	second, e := smsDecodePDU("004405912143F5000862011121436500080500037A02020440")
	if e != nil {
		t.Fatal(e)
	}
	if s.accept(second) != nil || len(s.messages()) != 1 || s.accept(first) != nil || len(s.messages()) != 2 {
		t.Fatal("out of order concat")
	}
	if s.messages()[0].(map[string]any)["text"] != "Пр" {
		t.Fatal("concat content")
	}
	id := s.messages()[0].(map[string]any)["id"].(string)
	if s.action("read", []string{id}) != nil || s.messages()[0].(map[string]any)["tag"] != "0" {
		t.Fatal("read")
	}
	if s.action("delete", []string{id}) != nil || s.accept(first) != nil || s.accept(second) != nil || len(s.messages()) != 1 {
		t.Fatal("deleted SMS replayed")
	}
	info, _ := os.Stat(s.path)
	if info.Mode().Perm() != 0600 {
		t.Fatal("private store")
	}
	s.path = filepath.Join(s.path, "unwritable")
	p.Hash = smsSIPHash("fsync-error")
	if s.accept(p) == nil || len(s.messages()) != 1 {
		t.Fatal("failed persistence acknowledged")
	}
}
func TestIMSOnlyNoCellularFallback(t *testing.T) {
	a := &App{settings: defaults()}
	a.settings.VoiceMode = "VOWIFI"
	if e := a.smsAction(nil, "send", nil, "12345", "hello", ""); e == nil || !strings.Contains(e.Error(), "fallback is disabled") {
		t.Fatal("unavailable did not fail closed")
	}
	a.smsIMS = testIMSStore(t)
	if e := a.smsAction(nil, "send", nil, "12345", "hello", ""); e == nil || !strings.Contains(e.Error(), "fallback is disabled") {
		t.Fatal("missing native service")
	}
}
func TestVoWiFiGSMCompatibilityUsesCellularOnce(t *testing.T) {
	sends := 0
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		r.ParseForm()
		switch {
		case r.Form.Get("cmd") == "loginfo":
			w.Write([]byte(`{"loginfo":"ok"}`))
		case r.Form.Get("cmd") == "wa_inner_version,cr_version,RD":
			w.Write([]byte(`{}`))
		case r.Form.Get("goformId") == "SEND_SMS":
			sends++
			w.Write([]byte(`{"result":"success"}`))
		case r.Form.Get("cmd") == "sms_cmd_status_info":
			w.Write([]byte(`{"sms_cmd_status_result":"3"}`))
		default:
			t.Error("unexpected cellular operation")
			w.WriteHeader(400)
		}
	}))
	defer backend.Close()
	a := &App{settings: defaults(), smsIMS: testIMSStore(t)}
	a.settings.VoiceMode = "VOWIFI_SMS"
	if e := a.smsAction(vendor(backend.URL), "send", nil, "12345", "fixture", ""); e != nil {
		t.Fatal(e)
	}
	if sends != 1 || len(a.smsIMS.state.Messages) != 0 {
		t.Fatal("compatibility SMS was duplicated or submitted to IMS")
	}
}
func TestIMSIPCUncertainNeverResent(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("SOCK_SEQPACKET production fixture runs on Linux")
	}
	s := testIMSStore(t)
	l, e := net.ListenUnix("unixpacket", &net.UnixAddr{Name: s.socket, Net: "unixpacket"})
	if e != nil {
		t.Fatal(e)
	}
	defer l.Close()
	count := 0
	go func() {
		for i := 0; i < 2; i++ {
			c, e := l.Accept()
			if e != nil {
				return
			}
			b := make([]byte, 410)
			n, _ := c.Read(b)
			if n >= 5 && b[4] == 1 {
				_, _ = c.Write(append([]byte{'M', 'S', 'I', '1', 0}, []byte(`{"ready":true}`)...))
			} else {
				count++
			}
			c.Close()
		}
	}()
	if e := s.send("12345", "hello"); e == nil {
		t.Fatal("EOF accepted")
	}
	if count != 1 || s.state.Messages[0].State != "uncertain" {
		t.Fatal("ambiguous submit")
	}
	if e := s.load(); e != nil || count != 1 || s.state.Messages[0].State != "uncertain" {
		t.Fatal("restart resent SMS")
	}
}
