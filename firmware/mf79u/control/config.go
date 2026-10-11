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
)

type SIP struct {
	Role                 string   `json:"role"`
	Extension            string   `json:"extension"`
	ExtensionPassword    string   `json:"extensionPassword,omitempty"`
	ExtensionPasswordSet bool     `json:"extensionPasswordSet,omitempty"`
	Server               string   `json:"server"`
	Port                 int      `json:"port"`
	Transport            string   `json:"transport"`
	Username             string   `json:"username"`
	Password             string   `json:"password,omitempty"`
	PasswordSet          bool     `json:"passwordSet,omitempty"`
	Realm                string   `json:"realm"`
	Register             bool     `json:"register"`
	IncomingUser         string   `json:"incomingUser"`
	LocalPort            int      `json:"localPort"`
	Bind                 string   `json:"bind"`
	TrustedPeers         []string `json:"trustedPeers"`
	Codecs               []string `json:"codecs"`
	CA                   string   `json:"ca,omitempty"`
}
type DHCPRoute struct {
	Destination string `json:"destination"`
	Gateway     string `json:"gateway"`
}
type Network struct {
	Subnet    string      `json:"subnet,omitempty"`
	PoolStart string      `json:"poolStart,omitempty"`
	PoolEnd   string      `json:"poolEnd,omitempty"`
	Routes    []DHCPRoute `json:"routes"`
	Mode      string      `json:"mode"`
	Address   string      `json:"address"`
	Gateway   string      `json:"gateway"`
	DNS       []string    `json:"dns"`
}
type WiFi struct {
	Mode        string  `json:"mode"`
	Enabled     bool    `json:"enabled"`
	Hidden      bool    `json:"hidden"`
	SSID        string  `json:"ssid"`
	Password    string  `json:"password,omitempty"`
	PasswordSet bool    `json:"passwordSet,omitempty"`
	Security    string  `json:"security"`
	Network     Network `json:"network"`
}
type VoWiFi struct {
	Uplink  string   `json:"uplink"`
	Gateway string   `json:"gateway"`
	DNS     []string `json:"dns"`
}

type Settings struct {
	Version          int      `json:"version"`
	VoiceMode        string   `json:"voiceMode"`
	VoWiFi           VoWiFi   `json:"vowifi"`
	Webhooks         Webhooks `json:"webhooks"`
	SIP              SIP      `json:"sip"`
	WiFi             WiFi     `json:"wifi"`
	InternetSharing  bool     `json:"internetSharing"`
	LAN              Network  `json:"lan"`
	BootstrapSeconds int      `json:"bootstrapSeconds"`
}

var hostRE = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$`)
var userRE = regexp.MustCompile(`^[A-Za-z0-9_.+~-]{1,64}$`)
var numberRE = regexp.MustCompile(`^\+?[0-9]{3,32}$`)

func defaults() Settings {
	return Settings{Version: 1, VoiceMode: "AUTO", BootstrapSeconds: 60, SIP: SIP{Role: "TRUNK", Extension: "100", Server: "192.168.0.169", Port: 5060, Transport: "UDP", Username: "mf79u", Realm: "*", IncomingUser: "mf79u", LocalPort: 5080, Bind: "0.0.0.0", TrustedPeers: []string{"192.168.0.169", "192.168.1.28"}, Codecs: []string{"OPUS", "G722", "PCMA", "PCMU", "G729"}}, WiFi: WiFi{Security: "WPA2", Network: Network{Mode: "DHCP", DNS: []string{}}}, LAN: Network{Mode: "STATIC", Address: "192.168.0.1/24", DNS: []string{}}}
}
func validateNetwork(n Network, lan bool) error {
	if n.Mode != "DHCP" && n.Mode != "STATIC" {
		return errors.New("Network mode must be DHCP or STATIC")
	}
	if lan && n.Mode == "DHCP" {
		return errors.New("USB LAN must keep a static management address. DHCP is available for Wi-Fi uplink.")
	}
	if n.Mode == "STATIC" {
		ip, _, e := net.ParseCIDR(n.Address)
		if e != nil || ip.To4() == nil {
			return errors.New("Enter an IPv4 address with a prefix, for example 192.168.1.50/24")
		}
	}
	if n.Gateway != "" && net.ParseIP(n.Gateway).To4() == nil {
		return errors.New("Invalid IPv4 gateway")
	}
	if len(n.DNS) > 3 {
		return errors.New("Use up to three DNS servers")
	}
	for _, d := range n.DNS {
		if net.ParseIP(d).To4() == nil {
			return errors.New("Invalid DNS address")
		}
	}
	return nil
}
func validate(s Settings) error {
	if e := validateTelegram(s.Webhooks.TelegramSMS); e != nil {
		return e
	}
	if e := validateVoWiFi(s.VoWiFi, s.LAN); e != nil {
		return e
	}
	if s.Version != 1 || s.BootstrapSeconds != 60 {
		return errors.New("Unsupported settings version")
	}
	if s.VoiceMode != "AUTO" && s.VoiceMode != "VOLTE" && s.VoiceMode != "CS" && s.VoiceMode != "VOWIFI" && s.VoiceMode != "VOWIFI_SMS" {
		return errors.New("Voice registration must be AUTO, VOLTE, CS, VOWIFI or VOWIFI_SMS")
	}
	p := s.SIP
	if p.Role != "" && p.Role != "TRUNK" && p.Role != "SERVER" && p.Role != "DISABLED" {
		return errors.New("SIP role must be DISABLED, TRUNK or SERVER")
	}
	if !userRE.MatchString(p.Extension) || len(p.ExtensionPassword) > 256 || strings.ContainsAny(p.ExtensionPassword, "\r\n\x00") {
		return errors.New("Invalid local SIP account")
	}
	if p.Role == "SERVER" {
		if len(p.ExtensionPassword) < 12 {
			return errors.New("Set a local SIP account password of at least 12 characters")
		}
		if p.Transport != "UDP" {
			return errors.New("Local SIP server currently supports UDP. Use trunk mode for TCP or TLS.")
		}
		if p.Bind == "0.0.0.0" && s.LAN.Mode != "STATIC" {
			return errors.New("Local SIP server requires a static LAN address")
		}
	}
	if strings.ContainsAny(p.Server+p.Username+p.IncomingUser, "\r\n\x00") ||
		(p.Role != "DISABLED" && p.Role != "SERVER" && (!hostRE.MatchString(p.Server) || !userRE.MatchString(p.Username) || !userRE.MatchString(p.IncomingUser))) {
		return errors.New("Invalid SIP server or username")
	}
	if p.Port < 1 || p.Port > 65535 || p.LocalPort < 1024 || p.LocalPort > 65535 {
		return errors.New("Invalid SIP port")
	}
	if p.Transport != "UDP" && p.Transport != "TCP" && p.Transport != "TLS" {
		return errors.New("SIP transport must be UDP, TCP or TLS")
	}
	if p.Bind != "0.0.0.0" && net.ParseIP(p.Bind).To4() == nil {
		return errors.New("Invalid local SIP address")
	}
	if len(p.Password) > 256 || strings.ContainsAny(p.Password, "\r\n\x00") || len(p.Realm) > 128 || strings.ContainsAny(p.Realm, "\r\n\x00") {
		return errors.New("Invalid SIP password or realm")
	}
	if len(p.TrustedPeers) > 8 {
		return errors.New("Use up to 8 trusted PBX addresses")
	}
	for _, ip := range p.TrustedPeers {
		if net.ParseIP(ip).To4() == nil {
			return errors.New("Trusted peers must be IPv4 addresses")
		}
	}
	if p.Role != "SERVER" && p.Role != "DISABLED" && !p.Register && len(p.TrustedPeers) == 0 {
		return errors.New("IP peer mode requires at least one trusted PBX address")
	}
	known := map[string]bool{"OPUS": true, "G722": true, "PCMA": true, "PCMU": true, "G729": true}
	seen := map[string]bool{}
	if (p.Role != "DISABLED" && len(p.Codecs) == 0) || len(p.Codecs) > 5 {
		return errors.New("Enable at least one SIP codec")
	}
	for _, c := range p.Codecs {
		if !known[c] || seen[c] {
			return errors.New("Unknown or duplicate SIP codec")
		}
		seen[c] = true
	}
	if len(p.CA) > 32768 || (p.CA != "" && !strings.Contains(p.CA, "-----BEGIN CERTIFICATE-----")) {
		return errors.New("The CA must be a PEM certificate up to 32 KiB")
	}
	w := s.WiFi
	if w.Mode != "" && w.Mode != "HOTSPOT" && w.Mode != "CLIENT" {
		return errors.New("Choose Wi-Fi Hotspot or Client mode")
	}
	if w.Enabled && (len(w.SSID) < 1 || len([]byte(w.SSID)) > 32) {
		return errors.New("SSID must be 1–32 bytes")
	}
	if strings.ContainsAny(w.SSID+w.Password, "\r\n\x00") {
		return errors.New("Invalid SSID or Wi-Fi password")
	}
	if w.Security != "WPA2" && !(w.Mode == "CLIENT" && w.Security == "OPEN") {
		return errors.New("Use WPA2-Personal, or Open in Client mode")
	}
	if w.Enabled && w.Security == "WPA2" && (len(w.Password) < 8 || len(w.Password) > 63) {
		return errors.New("WPA2 password must be 8–63 characters")
	}
	if e := validateNetwork(w.Network, false); e != nil {
		return e
	}
	if e := validateNetwork(s.LAN, true); e != nil {
		return e
	}
	return validateLAN(s.LAN)
}
func atomicFile(path string, data []byte, mode os.FileMode) error {
	if e := os.MkdirAll(filepath.Dir(path), 0700); e != nil {
		return e
	}
	f, e := os.CreateTemp(filepath.Dir(path), ".mf79u-")
	if e != nil {
		return e
	}
	name := f.Name()
	defer os.Remove(name)
	if e = f.Chmod(mode); e == nil {
		_, e = f.Write(data)
	}
	if e == nil {
		e = f.Sync()
	}
	ce := f.Close()
	if e == nil {
		e = ce
	}
	if e != nil {
		return e
	}
	if e = os.Rename(name, path); e != nil {
		return e
	}
	d, e := os.Open(filepath.Dir(path))
	if e == nil {
		e = d.Sync()
		d.Close()
	}
	return e
}
func readSettings(dir string) (Settings, error) {
	s := defaults()
	b, e := os.ReadFile(filepath.Join(dir, "settings.json"))
	if os.IsNotExist(e) {
		if e := migrateLAN(&s.LAN); e != nil {
			return s, e
		}
		return s, nil
	}
	if e != nil {
		return s, e
	}
	e = json.Unmarshal(b, &s)
	if e != nil {
		return s, e
	}
	if s.VoiceMode == "" {
		s.VoiceMode = "AUTO"
	}
	if s.WiFi.Mode == "" {
		// Former station credentials must never become a hotspot password.
		// Native startup loads the existing protected factory AP profile.
		s.WiFi = WiFi{Mode: "HOTSPOT", Security: "WPA2", Network: Network{Mode: "DHCP"}}
	}
	if e := migrateLAN(&s.LAN); e != nil {
		return s, e
	}
	return s, validate(s)
}
func publicSettings(s Settings) Settings {
	s.Webhooks.TelegramSMS.BotTokenSet = s.Webhooks.TelegramSMS.BotToken != ""
	s.Webhooks.TelegramSMS.BotToken = ""
	s.SIP.ExtensionPasswordSet = s.SIP.ExtensionPassword != ""
	s.SIP.ExtensionPassword = ""
	s.SIP.PasswordSet = s.SIP.Password != ""
	s.SIP.Password = ""
	s.WiFi.PasswordSet = s.WiFi.Password != ""
	s.WiFi.Password = ""
	return s
}
func gatewayINI(s Settings, dir string) []byte {
	p := s.SIP
	role := p.Role
	if role == "" {
		role = "TRUNK"
	}
	if role == "SERVER" {
		ip, _, _ := net.ParseCIDR(s.LAN.Address)
		p.Bind = ip.String()
	}
	ca := ""
	if p.CA != "" {
		ca = filepath.Join(dir, "ca.pem")
	}
	return []byte(fmt.Sprintf("role=%s\nextension=%s\nextension_password=%s\nserver=%s\nport=%d\ntransport=%s\nusername=%s\npassword=%s\nrealm=%s\nregister=%d\nincoming_user=%s\nlocal_port=%d\nbind=%s\ntrusted_peers=%s\ncodecs=%s\nca_file=%s\nvoice_mode=%s\nvowifi_uplink=%s\n", role, p.Extension, p.ExtensionPassword, p.Server, p.Port, p.Transport, p.Username, p.Password, p.Realm, btoi(p.Register), p.IncomingUser, p.LocalPort, p.Bind, strings.Join(p.TrustedPeers, ","), strings.Join(p.Codecs, ","), ca, s.VoiceMode, s.VoWiFi.Uplink))
}
func btoi(b bool) int {
	if b {
		return 1
	}
	return 0
}

func validateVoWiFi(v VoWiFi, lan Network) error {
	if v.Uplink != "" && v.Uplink != "WIFI" && v.Uplink != "USB" {
		return errors.New("VoWiFi uplink must be Wi-Fi or USB")
	}
	if v.Uplink != "USB" {
		return nil
	}
	own, subnet, e := net.ParseCIDR(lan.Address)
	gateway := net.ParseIP(v.Gateway).To4()
	if e != nil || gateway == nil || !subnet.Contains(gateway) || own.Equal(gateway) || !gateway.IsGlobalUnicast() || gateway.Equal(subnet.IP) {
		return errors.New("USB internet gateway must be another host in the management subnet")
	}
	broadcast := append(net.IP(nil), subnet.IP.To4()...)
	for i := range broadcast {
		broadcast[i] |= ^subnet.Mask[i]
	}
	if gateway.Equal(broadcast) {
		return errors.New("USB internet gateway cannot be the broadcast address")
	}
	if len(v.DNS) < 1 || len(v.DNS) > 3 {
		return errors.New("Enter one to three DNS servers for USB internet")
	}
	for _, d := range v.DNS {
		ip := net.ParseIP(d).To4()
		if ip == nil || !ip.IsGlobalUnicast() {
			return errors.New("Invalid USB DNS server")
		}
	}
	return nil
}
