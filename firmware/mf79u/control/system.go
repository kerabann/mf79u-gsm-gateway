package main

import (
	"context"
	"crypto/md5"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"syscall"
	"time"
)

const imeiLibraryMD5 = "27a21baf57d9ec55e21f62a44e9d8468"

var imeiRE = regexp.MustCompile(`^[0-9]{15}$`)
var cryptRE = regexp.MustCompile(`^\$6\$[./A-Za-z0-9]{8,16}\$[./A-Za-z0-9]{86}$`)

func validIMEI(s string) bool {
	if !imeiRE.MatchString(s) {
		return false
	}
	sum := 0
	for i, c := range []byte(s) {
		n := int(c - '0')
		if i%2 == 1 {
			n *= 2
			if n > 9 {
				n -= 9
			}
		}
		sum += n
	}
	return sum%10 == 0
}
func validSystemPassword(s string, min, max int) bool {
	if len(s) < min || len(s) > max {
		return false
	}
	for _, c := range s {
		if c < 32 || c > 126 {
			return false
		}
	}
	return true
}
func fileMD5(path string) string {
	f, e := os.Open(path)
	if e != nil {
		return ""
	}
	defer f.Close()
	h := md5.New()
	if _, e = io.Copy(h, f); e != nil {
		return ""
	}
	return hex.EncodeToString(h.Sum(nil))
}
func smallFile(path string) string {
	f, e := os.Open(path)
	if e != nil {
		return ""
	}
	defer f.Close()
	b, _ := io.ReadAll(io.LimitReader(f, 16384))
	return strings.TrimSpace(string(b))
}
func tailFile(path string, limit int) string {
	f, e := os.Open(path)
	if e != nil {
		return ""
	}
	defer f.Close()
	if s, e := f.Stat(); e == nil && s.Size() > int64(limit) {
		f.Seek(-int64(limit), io.SeekEnd)
	}
	b, _ := io.ReadAll(io.LimitReader(f, int64(limit)))
	return string(b)
}

var privateLogLine = regexp.MustCompile(`(?i)(password|authorization|cookie|nonce|\bimsi\b|\bimei\b|\biccid\b|\bautn\b|messagebody|sms[_ ]?(text|body)|\bsdp\b)`)
var logNumber = regexp.MustCompile(`\+?[0-9]{7,}`)
var logSIPUser = regexp.MustCompile(`(?i)(sips?:)[^\s<>@;]+@`)

func sanitizeLog(text string) string {
	lines := strings.Split(text, "\n")
	for i, line := range lines {
		if privateLogLine.MatchString(line) {
			lines[i] = "[private protocol data omitted]"
		} else {
			lines[i] = logNumber.ReplaceAllString(logSIPUser.ReplaceAllString(line, "${1}[redacted]@"), "[number]")
		}
	}
	return strings.Join(lines, "\n")
}
func (a *App) imeiRead() (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 23*time.Second)
	defer cancel()
	b, e := exec.CommandContext(ctx, filepath.Join(a.dir, "tools/system-imei"), "read").Output()
	s := strings.TrimSpace(string(b))
	if e != nil || !imeiRE.MatchString(s) {
		return "", errors.New("IMEI read unavailable")
	}
	return s, nil
}
func (a *App) system(w http.ResponseWriter, r *http.Request, s *Session) {
	path := strings.TrimPrefix(r.URL.Path, "/api/system/")
	if path == "info" && r.Method == "GET" {
		info := map[string]any{"model": "ZTE MF79U", "controlVersion": "0.10", "architecture": "ARMv7 soft-float (no VFP/NEON)", "pcm": "PCM16LE mono / 16000 Hz / 20 ms", "operatorCodecs": []string{"AMR-WB up to 23.85 kbit/s", "AMR-NB"}, "sipCodecs": []string{"Opus", "G.722", "G.711 A-law", "G.711 µ-law", "G.729"}, "native": a.native, "gateway": gatewayStatus(), "runtime": nativeRuntime(), "ssh": a.sshStatus()}
		if a.native {
			for key, path := range map[string]string{"kernel": "/proc/version", "cpu": "/proc/cpuinfo", "memory": "/proc/meminfo", "flashPartitions": "/proc/mtd", "uptimeSeconds": "/proc/uptime", "modules": "/proc/modules"} {
				info[key] = smallFile(path)
			}
			var wifiLines []string
			for _, line := range strings.Split(smallFile("/proc/wlan0/mib_rf"), "\n") {
				for _, field := range []string{"chipVersion:", "MIMO_TR_hw_support:"} {
					if strings.Contains(line, field) {
						wifiLines = append(wifiLines, strings.TrimSpace(line))
					}
				}
			}
			info["wifiHardware"] = strings.Join(wifiLines, "\n")
			info["sdCard"] = smallFile("/sys/block/mmcblk0/device/name") + " / " + smallFile("/sys/block/mmcblk0/size") + " sectors (512 bytes)"
			info["storage"] = output("df", "-k", "/mnt/userdata", filepath.Join(a.dir, "sd"))
			info["usbNetwork"] = output("ip", "-o", "addr", "show")
			info["busybox"] = toolVersion(filepath.Join(a.dir, "tools/busybox"), "--help")
			info["sshSoftware"] = toolVersion(filepath.Join(a.dir, "tools/dropbear"), "-V")
			info["imeiWriteAvailable"] = fileMD5("/lib/libatext.so") == imeiLibraryMD5
			a.systemmu.Lock()
			imei, e := a.imeiRead()
			a.systemmu.Unlock()
			if e == nil {
				info["imei"] = imei
			} else {
				info["imeiError"] = e.Error()
			}
		}
		radio, e := s.v.getAuthenticated(s.vendorKey, "wa_inner_version,cr_version,hardware_version,device_name")
		if e == nil {
			info["firmware"] = radio
		}
		respond(w, 200, info)
		return
	}
	if path == "logs" && r.Method == "GET" {
		source := r.URL.Query().Get("source")
		text := ""
		switch source {
		case "native":
			text = tailFile("/dev/.mf79u-native.log", 16384)
		case "ssh":
			text = tailFile("/dev/.mf79u-ssh.log", 16384)
		case "kernel":
			if a.native {
				text = output("dmesg")
				if len(text) > 16384 {
					text = text[len(text)-16384:]
				}
			}
		default:
			failure(w, 400, errors.New("Choose native, ssh or kernel logs"))
			return
		}
		respond(w, 200, map[string]any{"source": source, "text": sanitizeLog(text), "limitBytes": 16384, "redacted": true})
		return
	}
	if path == "ssh" && r.Method == "GET" {
		respond(w, 200, a.sshStatus())
		return
	}
	if (path == "ssh" && r.Method != "PUT") || (path != "ssh" && r.Method != "POST") {
		w.WriteHeader(405)
		return
	}
	if !a.native {
		failure(w, 409, errors.New("System changes require the native modem service"))
		return
	}
	a.systemmu.Lock()
	defer a.systemmu.Unlock()
	switch path {
	case "password":
		var value struct {
			CurrentPassword string `json:"currentPassword"`
			NewPassword     string `json:"newPassword"`
			ConfirmPassword string `json:"confirmPassword"`
		}
		if e := decode(w, r, &value); e != nil {
			failure(w, 400, e)
			return
		}
		if !validSystemPassword(value.NewPassword, 8, 32) || value.NewPassword != value.ConfirmPassword {
			failure(w, 400, errors.New("Use matching passwords with 8–32 printable ASCII characters"))
			return
		}
		current, newKey := sha(value.CurrentPassword), sha(value.NewPassword)
		value = struct {
			CurrentPassword string `json:"currentPassword"`
			NewPassword     string `json:"newPassword"`
			ConfirmPassword string `json:"confirmPassword"`
		}{}
		if subtle.ConstantTimeCompare([]byte(current), []byte(s.vendorKey)) != 1 {
			failure(w, 400, errors.New("Current administrator password is incorrect"))
			return
		}
		changed, e := s.v.changePassword(current, newKey)
		if !changed {
			failure(w, 502, e)
			return
		}
		// Re-authentication is mandatory after a credential change. Never retain the new key.
		a.mu.Lock()
		a.sessions = make(map[string]*Session)
		a.mu.Unlock()
		http.SetCookie(w, &http.Cookie{Name: "mf79u_session", Path: "/", MaxAge: -1, HttpOnly: true, SameSite: http.SameSiteStrictMode})
		if e != nil {
			failure(w, 502, e)
			return
		}
		respond(w, 200, map[string]bool{"ok": true, "signInRequired": true})
	case "imei":
		var value struct {
			IMEI    string `json:"imei"`
			Confirm bool   `json:"confirm"`
		}
		if e := decode(w, r, &value); e != nil {
			failure(w, 400, e)
			return
		}
		if !value.Confirm || !validIMEI(value.IMEI) {
			failure(w, 400, errors.New("Enter a valid 15-digit IMEI and confirm the change"))
			return
		}
		if gatewayBusy() {
			failure(w, 409, errors.New("End the active call first"))
			return
		}
		if fileMD5("/lib/libatext.so") != imeiLibraryMD5 || fileMD5(filepath.Join(a.dir, "libatext.vendor.b03.so")) != "d1ba655c5bc0ae566ea2a7b38fa0fbcd" {
			failure(w, 409, errors.New("Verified B03 IMEI patch and recovery library are required"))
			return
		}
		before, e := a.imeiRead()
		if e != nil {
			failure(w, 502, e)
			return
		}
		backup := filepath.Join(a.dir, "imei-before-system.json")
		if _, e = os.Stat(backup); os.IsNotExist(e) {
			b, _ := json.Marshal(map[string]string{"imei": before})
			if e = atomicFile(backup, b, 0600); e != nil {
				failure(w, 500, errors.New("Could not save the previous identity"))
				return
			}
		} else if e != nil {
			failure(w, 500, errors.New("Identity backup unavailable"))
			return
		}
		if gatewayBusy() {
			failure(w, 409, errors.New("A call became active; no change made"))
			return
		}
		ctx, cancel := context.WithTimeout(context.Background(), 23*time.Second)
		defer cancel()
		cmd := exec.CommandContext(ctx, filepath.Join(a.dir, "tools/system-imei"), "write")
		cmd.Stdin = strings.NewReader(value.IMEI + "\n")
		b, e := cmd.Output()
		if e != nil || strings.TrimSpace(string(b)) != "VERIFIED" {
			failure(w, 502, errors.New("IMEI write is unconfirmed. Refresh device information before retrying; no automatic retry was made"))
			return
		}
		respond(w, 200, map[string]any{"ok": true, "rebootRequired": true})
	case "reboot":
		var value struct {
			Confirm bool `json:"confirm"`
		}
		if e := decode(w, r, &value); e != nil {
			failure(w, 400, e)
			return
		}
		if !value.Confirm {
			failure(w, 400, errors.New("Confirm the reboot"))
			return
		}
		if gatewayBusy() {
			failure(w, 409, errors.New("End the active call first"))
			return
		}
		respond(w, 202, map[string]bool{"ok": true})
		go func() { time.Sleep(time.Second); _ = exec.Command("reboot").Run() }()
	case "ssh":
		var value struct {
			Enabled         bool   `json:"enabled"`
			Password        string `json:"password"`
			ConfirmPassword string `json:"confirmPassword"`
		}
		if e := decode(w, r, &value); e != nil {
			failure(w, 400, e)
			return
		}
		if value.Password != "" && (!validSystemPassword(value.Password, 12, 128) || value.Password != value.ConfirmPassword) {
			failure(w, 400, errors.New("Use matching SSH passwords with 12–128 printable ASCII characters"))
			return
		}
		if e := a.saveSSH(value.Enabled, value.Password); e != nil {
			failure(w, 400, e)
			return
		}
		value.Password = ""
		value.ConfirmPassword = ""
		respond(w, 200, a.sshStatus())
	default:
		w.WriteHeader(404)
	}
}
func (v *Vendor) changePassword(old, new string) (bool, error) {
	v.mu.Lock()
	defer v.mu.Unlock()
	if e := v.loginKeyLocked(old); e != nil {
		return false, errors.New("Current administrator password was rejected")
	}
	if _, e := v.post(url.Values{"goformId": {"CHANGE_PASSWORD"}, "oldPassword": {old}, "newPassword": {new}}); e != nil {
		return false, errors.New("The modem rejected the password change")
	}
	if e := v.loginKeyLocked(new); e != nil {
		return true, errors.New("Password change submitted but new sign-in is unconfirmed. Try the new password before retrying")
	}
	return true, nil
}

type sshConfig struct {
	Enabled bool `json:"enabled"`
}

func (a *App) readSSH() sshConfig {
	var c sshConfig
	json.Unmarshal([]byte(smallFile(filepath.Join(a.dir, "ssh.json"))), &c)
	return c
}
func (a *App) sshStatus() map[string]any {
	a.sshmu.Lock()
	defer a.sshmu.Unlock()
	c := a.readSSH()
	_, e := os.Stat(filepath.Join(a.dir, "tools/dropbear"))
	hash := smallFile(filepath.Join(a.dir, "ssh.password"))
	return map[string]any{"enabled": c.Enabled, "running": a.sshCmd != nil, "installed": e == nil, "passwordSet": cryptRE.MatchString(hash), "username": "admin", "port": 22, "error": a.sshError, "busyboxPath": filepath.Join(a.dir, "tools/busybox")}
}
func (a *App) saveSSH(enabled bool, password string) error {
	a.sshmu.Lock()
	defer a.sshmu.Unlock()
	if _, e := os.Stat(filepath.Join(a.dir, "tools/dropbear")); e != nil {
		return errors.New("SSH runtime is not installed")
	}
	if password != "" {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		cmd := exec.CommandContext(ctx, filepath.Join(a.dir, "tools/busybox"), "mkpasswd", "-m", "sha512", "-S", random()[:16])
		cmd.Stdin = strings.NewReader(password + "\n")
		b, e := cmd.Output()
		hash := strings.TrimSpace(string(b))
		if e != nil || !cryptRE.MatchString(hash) {
			return errors.New("Could not generate the SSH password hash")
		}
		if e = atomicFile(filepath.Join(a.dir, "ssh.password"), []byte(hash+"\n"), 0600); e != nil {
			return errors.New("Could not save the SSH password")
		}
		a.sshProfile = ""
	}
	if enabled && !cryptRE.MatchString(smallFile(filepath.Join(a.dir, "ssh.password"))) {
		return errors.New("Set an SSH password before enabling SSH")
	}
	b, _ := json.Marshal(sshConfig{enabled})
	if e := atomicFile(filepath.Join(a.dir, "ssh.json"), b, 0600); e != nil {
		return errors.New("Could not save SSH settings")
	}
	return a.reconcileSSHLocked()
}
func toolVersion(path string, args ...string) string {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	b, _ := exec.CommandContext(ctx, path, args...).CombinedOutput()
	return strings.Split(strings.TrimSpace(string(b)), "\n")[0]
}

// Login shells may create their own session/process group. Close only descendants
// of this owned Dropbear process, then the server, when SSH is disabled.
func stopOwnedSSH(pid int, dir string) {
	exe, _ := os.Readlink(fmt.Sprintf("/proc/%d/exe", pid))
	if pid < 2 || exe != filepath.Join(dir, "tools/dropbearmulti") {
		return
	}
	parents := map[int]int{}
	entries, _ := os.ReadDir("/proc")
	for _, entry := range entries {
		id, e := strconv.Atoi(entry.Name())
		if e != nil {
			continue
		}
		for _, line := range strings.Split(smallFile("/proc/"+entry.Name()+"/status"), "\n") {
			if strings.HasPrefix(line, "PPid:") {
				parent, _ := strconv.Atoi(strings.TrimSpace(strings.TrimPrefix(line, "PPid:")))
				parents[id] = parent
			}
		}
	}
	descendants := []int{}
	front := []int{pid}
	for len(front) > 0 {
		parent := front[0]
		front = front[1:]
		for id, p := range parents {
			if p == parent {
				descendants = append(descendants, id)
				front = append(front, id)
			}
		}
	}
	for i := len(descendants) - 1; i >= 0; i-- {
		syscall.Kill(descendants[i], syscall.SIGTERM)
	}
	syscall.Kill(pid, syscall.SIGTERM)
}
func (a *App) stopSSHLocked() {
	if a.sshCmd != nil {
		stopOwnedSSH(a.sshCmd.Process.Pid, a.dir)
		a.sshCmd = nil
	}
	a.sshProfile = ""
	os.Remove("/dev/.mf79u-ssh.pid")
}
func (a *App) reconcileSSHLocked() error {
	c := a.readSSH()
	a.mu.Lock()
	gateway := a.settings.LAN.Gateway
	a.mu.Unlock()
	profile := gateway
	if !c.Enabled {
		a.stopSSHLocked()
		a.sshError = ""
		return nil
	}
	if a.sshCmd != nil {
		select {
		case <-a.sshDone:
			a.stopSSHLocked()
			a.sshError = "SSH exited; check the SSH log"
		default:
		}
	}
	if a.sshCmd != nil && syscall.Kill(a.sshCmd.Process.Pid, 0) != nil {
		a.stopSSHLocked()
	}
	if a.sshCmd != nil && a.sshProfile == profile {
		return nil
	}
	a.stopSSHLocked()
	fail := func(message string) error { a.sshError = message; return errors.New(message) }
	if !cryptRE.MatchString(smallFile(filepath.Join(a.dir, "ssh.password"))) {
		return fail("SSH requires a saved password")
	}
	if net.ParseIP(gateway) == nil {
		return fail("SSH LAN address is invalid")
	}
	hostKey := filepath.Join(a.dir, "ssh-host-ed25519")
	if _, e := os.Stat(hostKey); os.IsNotExist(e) {
		stage := hostKey + ".next"
		os.Remove(stage)
		if e = run(filepath.Join(a.dir, "tools/dropbearkey"), "-t", "ed25519", "-f", stage); e != nil {
			return fail("SSH host key generation failed")
		}
		os.Chmod(stage, 0600)
		if e = os.Rename(stage, hostKey); e != nil {
			return fail("Could not save SSH host key")
		}
	}
	logpath := "/dev/.mf79u-ssh.log"
	if f, e := os.OpenFile(logpath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0600); e == nil {
		cmd := exec.Command(filepath.Join(a.dir, "tools/dropbear"), "-F", "-r", hostKey, "-p", gateway+":22", "-p", "127.0.0.1:22", "-P", "/dev/.mf79u-ssh.pid", "-j", "-k", "-I", "600", "-K", "30")
		cmd.Stdout = f
		cmd.Stderr = f
		cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
		e = cmd.Start()
		f.Close()
		if e != nil {
			return fail("SSH could not start; check the SSH log")
		}
		a.sshCmd = cmd
		a.sshProfile = profile
		a.sshError = ""
		done := make(chan error, 1)
		a.sshDone = done
		go func() { done <- cmd.Wait() }()
		time.Sleep(150 * time.Millisecond)
		select {
		case <-done:
			a.sshCmd = nil
			a.sshProfile = ""
			return fail("SSH startup failed; check the SSH log")
		default:
		}
		return nil
	}
	return fail("SSH log unavailable")
}
func (a *App) maintainSSH() {
	// Remove only a previous owned server from a control daemon restart.
	pid, _ := strconv.Atoi(smallFile("/dev/.mf79u-ssh.pid"))
	if pid > 1 {
		exe, _ := os.Readlink(fmt.Sprintf("/proc/%d/exe", pid))
		group, _ := syscall.Getpgid(pid)
		if exe == filepath.Join(a.dir, "tools/dropbearmulti") && group == pid {
			stopOwnedSSH(pid, a.dir)
		}
	}
	for {
		a.sshmu.Lock()
		_ = a.reconcileSSHLocked()
		a.sshmu.Unlock()
		if st, e := os.Stat("/dev/.mf79u-ssh.log"); e == nil && st.Size() > 65536 {
			os.Truncate("/dev/.mf79u-ssh.log", 0)
		}
		time.Sleep(3 * time.Second)
	}
}
