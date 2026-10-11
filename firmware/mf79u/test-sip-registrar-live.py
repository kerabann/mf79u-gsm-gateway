#!/usr/bin/env python3
"""Exercise the physical MF79U registrar without reaching the SIM dial path.

The current gateway configuration is restored in a finally block.  The test
uses a random one-run password and a deliberately nonnumeric INVITE target.
No credentials or SIP messages are printed.
"""

import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
ADB = os.path.join(ROOT, "outputs", "adb")
REMOTE_DIR = "/mnt/userdata/mf79u"
CONFIG = REMOTE_DIR + "/gateway.ini"
BACKUP = REMOTE_DIR + "/gateway.ini.pre-registrar-live-test"
STAGING = REMOTE_DIR + "/gateway.ini.registrar-test.new"
MODEM = "192.168.0.1"
PORT = 5080


def adb(*args, input_data=None):
    return subprocess.run(
        [ADB, *args], input=input_data, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=True,
    ).stdout


def shell(command):
    return adb("shell", command).decode(errors="replace")


def status():
    return json.loads(shell("cat /dev/.mf79u-gateway-status.json"))


def wait_role(role, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            current = status()
            if current.get("role") == role and current.get("running"):
                return current
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            pass
        time.sleep(0.25)
    raise TimeoutError("gateway did not enter the requested role")


def parse_config(raw):
    result = {}
    for line in raw.decode().splitlines():
        key, separator, value = line.partition("=")
        if not separator:
            raise ValueError("invalid gateway configuration")
        result[key] = value
    return result


def encode_config(config):
    order = (
        "role", "extension", "extension_password", "server", "port",
        "transport", "username", "password", "realm", "register",
        "incoming_user", "local_port", "bind", "trusted_peers", "codecs",
        "ca_file",
    )
    if set(config) != set(order):
        raise ValueError("unexpected gateway configuration fields")
    return "".join(f"{key}={config[key]}\n" for key in order).encode()


def md5(value):
    return hashlib.md5(value.encode()).hexdigest()


def sip_message(method, uri, local_ip, local_port, call_id, cseq, auth="", body=""):
    lines = [
        f"{method} {uri} SIP/2.0",
        f"Via: SIP/2.0/UDP {local_ip}:{local_port};branch=z9hG4bK-{call_id}-{cseq};rport",
        "Max-Forwards: 70",
        f"From: <sip:100@{local_ip}>;tag={call_id}",
        f"To: <sip:100@{local_ip}>",
        f"Call-ID: {call_id}",
        f"CSeq: {cseq} {method}",
        f"Contact: <sip:100@{local_ip}:{local_port}>",
    ]
    if method == "REGISTER":
        lines.append("Expires: 120")
    if auth:
        lines.append("Authorization: " + auth)
    if body:
        lines.append("Content-Type: application/sdp")
    lines += [f"Content-Length: {len(body.encode())}", "", body]
    return "\r\n".join(lines).encode()


def final_reply(sock, payload):
    sock.sendto(payload, (MODEM, PORT))
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        data, _ = sock.recvfrom(65535)
        match = re.match(br"SIP/2.0 (\d{3})", data)
        if match and int(match.group(1)) >= 200:
            return int(match.group(1)), data.decode(errors="replace")
    raise TimeoutError("SIP response timed out")


def challenge(sock, local_ip, call_id):
    uri = f"sip:{MODEM}:{PORT}"
    request = sip_message("REGISTER", uri, local_ip, sock.getsockname()[1], call_id, 1)
    code, text = final_reply(sock, request)
    nonce = re.search(r'nonce="([0-9a-f]{32})"', text)
    if code != 401 or not nonce or 'qop="auth"' not in text:
        raise AssertionError("registrar did not issue a complete digest challenge")
    return uri, nonce.group(1)


def authorization(password, method, uri, nonce, nc):
    cnonce = secrets.token_hex(8)
    ha1 = md5("100:mf79u:" + password)
    ha2 = md5(method + ":" + uri)
    digest = md5(ha1 + ":" + nonce + ":" + nc + ":" + cnonce + ":auth:" + ha2)
    return (
        f'Digest username="100", realm="mf79u", nonce="{nonce}", '
        f'uri="{uri}", response="{digest}", algorithm=MD5, '
        f'qop=auth, nc={nc}, cnonce="{cnonce}"'
    )


def signal_reload():
    current = status()
    pid = int(current["pid"])
    shell(f"kill -HUP {pid}")


def main():
    if not os.path.isfile(ADB):
        raise SystemExit("adb helper is missing")
    # This device uses an old adb implementation without exec-out support.
    # gateway.ini values cannot contain newlines, so shell cat is lossless.
    original = adb("shell", "cat " + CONFIG).replace(b"\r\n", b"\n")
    config = parse_config(original)
    if status().get("activeCall"):
        raise SystemExit("refusing registrar test during an active call")

    password = secrets.token_urlsafe(24)
    test_config = dict(config)
    test_config.update({
        "role": "SERVER", "extension": "100",
        "extension_password": password, "transport": "UDP",
        "local_port": str(PORT), "bind": MODEM,
    })

    installed = False
    restored = False
    result = None
    try:
        shell(f"rm -f {BACKUP} {STAGING}; cp {CONFIG} {BACKUP}; chmod 600 {BACKUP}")
        with tempfile.NamedTemporaryFile(prefix="mf79u-registrar-", delete=False) as stream:
            temporary = stream.name
            stream.write(encode_config(test_config))
        try:
            os.chmod(temporary, 0o600)
            adb("push", temporary, STAGING)
        finally:
            os.unlink(temporary)
        shell(f"chmod 600 {STAGING}; mv {STAGING} {CONFIG}")
        installed = True
        signal_reload()
        wait_role("SERVER")

        route = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        route.connect((MODEM, PORT))
        local_ip = route.getsockname()[0]
        route.close()
        if local_ip == "127.0.0.1":
            raise AssertionError("registrar test selected loopback")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((local_ip, 0))
        sock.settimeout(2)
        try:
            register_uri, nonce = challenge(sock, local_ip, "live-register")
            auth = authorization(password, "REGISTER", register_uri, nonce, "00000001")
            request = sip_message("REGISTER", register_uri, local_ip, sock.getsockname()[1], "live-register", 2, auth)
            code, _ = final_reply(sock, request)
            if code != 200:
                raise AssertionError("authenticated live REGISTER was rejected")
            current = status()
            if not current.get("localRegistered") or current.get("localRegistrationExpires", 0) <= 0:
                raise AssertionError("live binding was not exposed in gateway status")

            invite_uri = f"sip:probe@{MODEM}:{PORT}"
            invite_auth = authorization(password, "INVITE", invite_uri, nonce, "00000002")
            sdp = (
                f"v=0\r\no=- 1 1 IN IP4 {local_ip}\r\ns=MF79U live test\r\n"
                f"c=IN IP4 {local_ip}\r\nt=0 0\r\nm=audio 20000 RTP/AVP 0\r\n"
                "a=rtpmap:0 PCMU/8000\r\na=sendrecv\r\n"
            )
            request = sip_message("INVITE", invite_uri, local_ip, sock.getsockname()[1], "safe-live-probe", 1, invite_auth, sdp)
            code, _ = final_reply(sock, request)
            if code != 484:
                raise AssertionError("nonnumeric live destination did not stop before the SIM dial path")
            if status().get("activeCall"):
                raise AssertionError("safe live probe unexpectedly created a call")
        finally:
            sock.close()

        result = {
            "authenticatedRegister": True,
            "bindingVisible": True,
            "physicalModem": True,
            "safeDestinationRejected": True,
            "simCalls": False,
        }
    finally:
        if installed:
            try:
                shell(f"test -s {BACKUP}; mv {BACKUP} {CONFIG}; rm -f {STAGING}")
                restored = True
                signal_reload()
                wait_role(config.get("role", "TRUNK"))
            finally:
                if restored:
                    shell(f"rm -f {BACKUP}")
    if result is None or not restored:
        raise RuntimeError("live registrar test did not restore the original configuration")
    result.update({
        "testedAt": datetime.now(timezone.utc).isoformat(),
        "artifactSha256": hashlib.sha256((BUILD / "modem-sip-gateway").read_bytes()).hexdigest(),
        "configurationRestored": True,
        "restoredRole": config.get("role", "TRUNK"),
    })
    (BUILD / "sip-registrar-live.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in (
        "authenticatedRegister", "bindingVisible", "configurationRestored",
        "physicalModem", "safeDestinationRejected", "simCalls",
    )}, sort_keys=True))


if __name__ == "__main__":
    main()
