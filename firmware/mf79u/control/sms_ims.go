package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"
)

const smsIMSPath = "/dev/.mf79u-sms-ims.sock"

var imsSMSID = regexp.MustCompile(`^ims-[a-f0-9]{32}$`)

type imsSMSMessage struct{ ID, Number, Text, Date, Tag, State string }
type imsSMSState struct {
	Messages []imsSMSMessage
	Parts    []imsSMSPart
	Seen     []string
}
type imsSMSStore struct {
	mu                  sync.Mutex
	sendMu              sync.Mutex
	state               imsSMSState
	path, spool, socket string
}

func imsSMSIPC(path string, op byte, payload string) ([]byte, error) {
	c, e := net.DialTimeout("unixpacket", path, time.Second)
	if e != nil {
		return nil, errors.New("VoWiFi SMS service unavailable; cellular SMS fallback is disabled")
	}
	defer c.Close()
	_ = c.SetDeadline(time.Now().Add(60 * time.Second))
	packet := append([]byte{'M', 'S', 'I', '1', op}, []byte(payload)...)
	if n, e := c.Write(packet); e != nil || n != len(packet) {
		return nil, errors.New("VoWiFi SMS submission is unconfirmed. Check delivery before sending again.")
	}
	out := make([]byte, 4096)
	n, e := c.Read(out)
	if e != nil || n < 5 || string(out[:4]) != "MSI1" {
		return nil, errors.New("VoWiFi SMS submission is unconfirmed. Check delivery before sending again.")
	}
	switch out[4] {
	case 0:
		return out[5:n], nil
	case 2:
		return nil, errors.New("VoWiFi SMS is not registered; cellular SMS fallback is disabled")
	case 3:
		return nil, errors.New("Another VoWiFi SMS is in progress")
	case 6:
		return nil, errors.New("The IMS network rejected SMS submission. Check delivery before sending again.")
	case 7:
		return nil, errors.New("VoWiFi SMS submission is unconfirmed. Check delivery before sending again.")
	default:
		return nil, errors.New("Invalid VoWiFi SMS request")
	}
}
func (s *imsSMSStore) saveLocked() error {
	b, e := json.Marshal(s.state)
	if e != nil {
		return e
	}
	return atomicFile(s.path, b, 0600)
}
func (s *imsSMSStore) load() error {
	b, e := os.ReadFile(s.path)
	if os.IsNotExist(e) {
		return nil
	}
	if e != nil {
		return e
	}
	if len(b) > 1000000 || json.Unmarshal(b, &s.state) != nil || len(s.state.Messages) > 128 || len(s.state.Parts) > 256 || len(s.state.Seen) > 512 {
		return errors.New("Invalid IMS SMS store")
	}
	for i := range s.state.Messages {
		if s.state.Messages[i].State == "sending" {
			s.state.Messages[i].State = "uncertain"
		}
	}
	return s.saveLocked()
}
func (s *imsSMSStore) accept(p imsSMSPart) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, h := range s.state.Seen {
		if h == p.Hash {
			return nil
		}
	}
	// Work on a copy so a failed fsync cannot acknowledge an unsaved message.
	next := s.state
	next.Messages = append([]imsSMSMessage(nil), next.Messages...)
	next.Parts = append([]imsSMSPart(nil), next.Parts...)
	next.Seen = append([]string(nil), next.Seen...)
	if !p.Report {
		if p.Total == 1 {
			if len(next.Messages) >= 128 {
				return errors.New("IMS inbox full")
			}
			next.Messages = append(next.Messages, imsSMSMessage{ID: "ims-" + p.Hash, Number: p.Number, Text: p.Text, Date: p.Date, Tag: "1", State: "received"})
		} else {
			if len(next.Parts) >= 256 {
				return errors.New("IMS multipart store full")
			}
			for _, part := range next.Parts {
				if part.Group == p.Group && part.Sequence == p.Sequence {
					return errors.New("Ambiguous multipart SMS reference")
				}
			}
			next.Parts = append(next.Parts, p)
			parts := make([]imsSMSPart, p.Total)
			found := 0
			for _, part := range next.Parts {
				if part.Group == p.Group {
					parts[part.Sequence-1] = part
					found++
				}
			}
			if found == p.Total {
				if len(next.Messages) >= 128 {
					return errors.New("IMS inbox full")
				}
				var text strings.Builder
				for _, part := range parts {
					text.WriteString(part.Text)
				}
				if len(text.String()) > smsIncomingTextLimit {
					return errors.New("IMS SMS exceeds text limit")
				}
				next.Messages = append(next.Messages, imsSMSMessage{ID: "ims-" + smsSIPHash(parts[0].Hash+parts[len(parts)-1].Hash), Number: p.Number, Text: text.String(), Date: parts[0].Date, Tag: "1", State: "received"})
				retained := []imsSMSPart{}
				for _, part := range next.Parts {
					if part.Group != p.Group {
						retained = append(retained, part)
					}
				}
				next.Parts = retained
			}
		}
	}
	next.Seen = append(next.Seen, p.Hash)
	if len(next.Seen) > 512 {
		next.Seen = next.Seen[len(next.Seen)-512:]
	}
	old := s.state
	s.state = next
	if e := s.saveLocked(); e != nil {
		s.state = old
		return e
	}
	return nil
}
func (s *imsSMSStore) importSpool() {
	files, e := os.ReadDir(s.spool)
	if e != nil {
		return
	}
	for _, f := range files {
		if f.IsDir() || !strings.HasSuffix(f.Name(), ".pdu") {
			continue
		}
		path := filepath.Join(s.spool, f.Name())
		info, e := os.Lstat(path)
		if e != nil || !info.Mode().IsRegular() || info.Size() > 400 {
			continue
		}
		b, e := os.ReadFile(path)
		if e != nil {
			continue
		}
		part, e := smsDecodePDU(string(b))
		if e != nil {
			_ = os.Rename(path, strings.TrimSuffix(path, ".pdu")+".unsupported")
			continue
		} // retain original PDU privately
		if s.accept(part) == nil {
			_ = os.Remove(path)
		}
	}
}
func (s *imsSMSStore) messages() []any {
	s.importSpool()
	s.mu.Lock()
	defer s.mu.Unlock()
	out := []any{}
	for i := len(s.state.Messages) - 1; i >= 0; i-- {
		m := s.state.Messages[i]
		out = append(out, map[string]any{"id": m.ID, "number": m.Number, "text": m.Text, "date": m.Date, "tag": m.Tag, "transport": "SMSoIP", "submission": m.State})
	}
	return out
}
func (s *imsSMSStore) action(action string, ids []string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(ids) < 1 || len(ids) > 100 {
		return errors.New("Select messages")
	}
	selected := map[string]bool{}
	for _, id := range ids {
		if !imsSMSID.MatchString(id) {
			return errors.New("Invalid SMS ID")
		}
		selected[id] = true
	}
	old := s.state.Messages
	next := []imsSMSMessage{}
	for _, m := range old {
		if selected[m.ID] {
			if m.State == "sending" {
				return errors.New("SMS submission is still in progress")
			}
			if action == "delete" {
				continue
			}
			if m.Tag == "1" {
				m.Tag = "0"
			}
		}
		next = append(next, m)
	}
	s.state.Messages = next
	if e := s.saveLocked(); e != nil {
		s.state.Messages = old
		return e
	}
	return nil
}
func (s *imsSMSStore) send(number, text string) error {
	s.sendMu.Lock()
	defer s.sendMu.Unlock()
	pdus, e := smsSubmitPDUs(number, text)
	if e != nil {
		return e
	}
	status, e := imsSMSIPC(s.socket, 1, "")
	if e != nil {
		return e
	}
	var readiness struct{ Ready bool }
	if json.Unmarshal(status, &readiness) != nil || !readiness.Ready {
		return errors.New("VoWiFi SMS is not ready; cellular SMS fallback is disabled")
	}
	id := "ims-" + smsSIPHash(random())
	s.mu.Lock()
	if len(s.state.Messages) >= 128 {
		s.mu.Unlock()
		return errors.New("IMS inbox full; delete old messages before sending")
	}
	s.state.Messages = append(s.state.Messages, imsSMSMessage{ID: id, Number: number, Text: text, Date: time.Now().Format(time.RFC3339), Tag: "2", State: "sending"})
	e = s.saveLocked()
	if e != nil {
		s.state.Messages = s.state.Messages[:len(s.state.Messages)-1]
	}
	s.mu.Unlock()
	if e != nil {
		return e
	}
	for i, pdu := range pdus {
		_, e = imsSMSIPC(s.socket, 2, pdu)
		if e != nil {
			if i > 0 {
				e = fmt.Errorf("Some SMS parts were accepted by IMS; completion is unconfirmed. Check delivery before sending again.")
			}
			break
		}
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	for i := range s.state.Messages {
		if s.state.Messages[i].ID == id {
			s.state.Messages[i].State = "accepted"
			if e != nil {
				s.state.Messages[i].State = "uncertain"
			}
		}
	}
	if persist := s.saveLocked(); persist != nil && e == nil {
		e = errors.New("IMS accepted the SMS, but local history could not be saved. Do not resend.")
	}
	return e
}
func (a *App) startSMSIMS() error {
	s := &imsSMSStore{path: filepath.Join(a.dir, "sms-ims-state.json"), spool: filepath.Join(a.dir, "sms-ims-spool"), socket: smsIMSPath}
	if e := s.load(); e != nil {
		return e
	}
	a.smsIMS = s
	go func() {
		for {
			s.importSpool()
			time.Sleep(time.Second)
		}
	}()
	return nil
}
func (a *App) smsList(v *Vendor, storage, key string) (map[string]any, error) {
	value, e := v.sms(storage, key)
	if e != nil {
		return nil, e
	}
	if storage == "modem" && a.smsIMS != nil {
		messages := a.smsIMS.messages()
		value["messages"] = append(value["messages"].([]any), messages...)
		value["imsCapacity"] = map[string]any{"used": len(messages), "total": 128}
	}
	a.mu.Lock()
	only := a.settings.VoiceMode == "VOWIFI"
	gsm := a.settings.VoiceMode == "VOWIFI_SMS"
	a.mu.Unlock()
	value["transport"] = "cellular"
	if only {
		value["transport"] = "SMSoIP"
	} else if gsm {
		value["transport"] = "GSM"
	}
	return value, nil
}
func validSMSID(id string) bool { return regexpID.MatchString(id) || imsSMSID.MatchString(id) }
func (a *App) smsAction(v *Vendor, action string, ids []string, number, text, key string) error {
	if action == "send" {
		a.mu.Lock()
		only := a.settings.VoiceMode == "VOWIFI"
		a.mu.Unlock()
		if only {
			if a.smsIMS == nil {
				return errors.New("VoWiFi SMS service unavailable; cellular SMS fallback is disabled")
			}
			return a.smsIMS.send(number, text)
		}
		return v.smsAction(action, ids, number, text, key)
	}
	if action != "read" && action != "delete" {
		return errors.New("Unknown SMS operation")
	}
	if len(ids) < 1 || len(ids) > 100 {
		return errors.New("Select messages")
	}
	var local, cellular []string
	for _, id := range ids {
		if !validSMSID(id) {
			return errors.New("Invalid SMS ID")
		}
		if imsSMSID.MatchString(id) {
			local = append(local, id)
		} else {
			cellular = append(cellular, id)
		}
	}
	if len(local) > 0 {
		if a.smsIMS == nil {
			return errors.New("IMS SMS store unavailable")
		}
		if e := a.smsIMS.action(action, local); e != nil {
			return e
		}
	}
	if len(cellular) > 0 {
		return v.smsAction(action, cellular, "", "", key)
	}
	return nil
}
