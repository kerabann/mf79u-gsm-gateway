#!/usr/bin/env python3
"""Isolated one-account registrar test. It cannot access the modem or place a SIM call."""
import argparse
import hashlib
import json
import os
import queue
import re
import signal
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path


def md5(value):
    return hashlib.md5(value.encode()).hexdigest()


def response(password, method, uri, nonce, nc, cnonce):
    ha1 = md5("100:mf79u:" + password)
    ha2 = md5(method + ":" + uri)
    return md5(ha1 + ":" + nonce + ":" + nc + ":" + cnonce + ":auth:" + ha2)


def message(method, uri, host, port, call_id, cseq, contact=True, authorization="", body=""):
    lines = [
        f"{method} {uri} SIP/2.0",
        f"Via: SIP/2.0/UDP {host}:{port};branch=z9hG4bK-{call_id}-{cseq};rport",
        "Max-Forwards: 70",
        f"From: <sip:100@{host}>;tag={call_id}",
        f"To: <sip:100@{host}>",
        f"Call-ID: {call_id}",
        f"CSeq: {cseq} {method}",
    ]
    if contact:
        lines.append(f"Contact: <sip:100@{host}:{port}>")
        if method == "REGISTER":
            lines.append("Expires: 300")
    if authorization:
        lines.append("Authorization: " + authorization)
    if body:
        lines.append("Content-Type: application/sdp")
    lines += [f"Content-Length: {len(body.encode())}", "", body]
    return "\r\n".join(lines).encode()


def final_reply(sock, payload, target):
    sock.sendto(payload, target)
    expected = [re.search(br"(?im)^" + name + br":\s*([^\r\n]+)", payload).group(1) for name in (b"Call-ID", b"CSeq")]
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        data, _ = sock.recvfrom(65535)
        observed = [re.search(br"(?im)^" + name + br":\s*([^\r\n]+)", data) for name in (b"Call-ID", b"CSeq")]
        if any(value is None or value.group(1) != wanted for value, wanted in zip(observed, expected)):
            continue
        match = re.match(br"SIP/2.0 (\d{3})", data)
        if match and int(match.group(1)) >= 200:
            return int(match.group(1)), data.decode(errors="replace")
    raise TimeoutError("SIP final response timed out")


def challenge(sock, host, target, call_id):
    uri = f"sip:{host}:15080"
    code, text = final_reply(sock, message("REGISTER", uri, host, sock.getsockname()[1], call_id, 1), target)
    if code != 401:
        raise AssertionError(f"expected 401, got {code}")
    nonce = re.search(r'nonce="([0-9a-f]{32})"', text)
    if not nonce or 'qop="auth"' not in text or "algorithm=MD5" not in text:
        raise AssertionError("incomplete digest challenge")
    return uri, nonce.group(1)


def auth_header(password, method, uri, nonce, nc):
    cnonce = "0123456789abcdef"
    digest = response(password, method, uri, nonce, nc, cnonce)
    return (f'Digest username="100", realm="mf79u", nonce="{nonce}", '
            f'uri="{uri}", response="{digest}", algorithm=MD5, '
            f'qop=auth, nc={nc}, cnonce="{cnonce}"')


def register(sock, host, target, call_id):
    password = "local-lab-password"
    uri, nonce = challenge(sock, host, target, call_id)
    auth = auth_header(password, "REGISTER", uri, nonce, "00000001")
    code, _ = final_reply(sock, message("REGISTER", uri, host, sock.getsockname()[1], call_id, 2, authorization=auth), target)
    if code != 200:
        raise AssertionError(f"authenticated REGISTER failed: {code}")
    return nonce


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--backend",choices=("ims","cs"),default="ims")
    args = parser.parse_args()
    host = socket.gethostbyname(socket.gethostname())
    target = (host, 15080)
    with tempfile.TemporaryDirectory(prefix="mf79u-registrar-") as temporary:
        config = os.path.join(temporary, "gateway.ini")
        with open(config, "w", encoding="utf-8") as stream:
            stream.write(
                "role=SERVER\nextension=100\nextension_password=local-lab-password\n"
                "server=127.0.0.1\nport=5060\ntransport=UDP\nusername=mf79u\n"
                "password=\nrealm=*\nregister=0\nincoming_user=mf79u\nlocal_port=15080\n"
                f"bind={host}\ntrusted_peers=127.0.0.1\n"
                "codecs=OPUS,G722,PCMA,PCMU,G729\nca_file=\nvoice_mode=VOWIFI\nvowifi_uplink=USB\n"
            )
        process = subprocess.Popen(
            [args.gateway, "--wideband", "--config", config],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        lines = queue.Queue()
        thread = threading.Thread(target=lambda: [lines.put(line.rstrip()) for line in process.stdout], daemon=True)
        thread.start()
        deadline = time.monotonic() + 8
        observed = []
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=.2)
            except queue.Empty:
                continue
            observed.append(line)
            if line == "GATEWAY_LISTENING":
                break
        else:
            raise RuntimeError("gateway did not start: " + "; ".join(observed[-5:]))
        process.stdin.write("BACKEND cs\n" if args.backend=="cs" else "READY\n")
        process.stdin.flush()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=.2)
            except queue.Empty:
                continue
            observed.append(line)
            if line == "GATEWAY_READY":
                break
        else:
            raise RuntimeError("gateway did not become ready")
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            status = json.loads(Path("/dev/.mf79u-gateway-status.json").read_text())
            if status.get("voiceReady") and status.get("voiceBackend") == args.backend:
                break
            time.sleep(.05)
        else:
            raise AssertionError("backend readiness status missing")
        assert status["imsReady"] == (args.backend == "ims")
        first = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        second = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        invalid = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for sock in (first, second, invalid):
            sock.bind((host, 0))
            sock.settimeout(2)
        try:
            register(first, host, target, "first-binding")
            second_nonce = register(second, host, target, "second-binding")

            register_uri = f"sip:{host}:15080"
            replay = auth_header("local-lab-password", "REGISTER", register_uri, second_nonce, "00000001")
            code, text = final_reply(second, message("REGISTER", register_uri, host, second.getsockname()[1], "second-binding", 3, authorization=replay), target)
            if code != 401 or "stale=true" not in text:
                raise AssertionError("digest nonce count replay was not rejected")

            invalid_uri, invalid_nonce = challenge(invalid, host, target, "invalid-password")
            invalid_auth = auth_header("incorrect-password", "REGISTER", invalid_uri, invalid_nonce, "00000001")
            code, _ = final_reply(invalid, message("REGISTER", invalid_uri, host, invalid.getsockname()[1], "invalid-password", 2, authorization=invalid_auth), target)
            if code != 403:
                raise AssertionError("invalid local SIP password was accepted")

            invite_uri = f"sip:probe@{host}:15080"
            first_uri, first_nonce = challenge(first, host, target, "first-after-replace")
            first_auth = auth_header("local-lab-password", "INVITE", invite_uri, first_nonce, "00000001")
            sdp = (f"v=0\r\no=- 1 1 IN IP4 {host}\r\ns=MF79U test\r\n"
                   f"c=IN IP4 {host}\r\nt=0 0\r\nm=audio 20000 RTP/AVP 0\r\n"
                   "a=rtpmap:0 PCMU/8000\r\na=sendrecv\r\n")
            code, _ = final_reply(first, message("INVITE", invite_uri, host, first.getsockname()[1], "first-invite", 1, True, first_auth, sdp), target)
            if code != 480:
                raise AssertionError(f"replaced client was not rejected: {code}")

            second_auth = auth_header("local-lab-password", "INVITE", invite_uri, second_nonce, "00000002")
            code, _ = final_reply(second, message("INVITE", invite_uri, host, second.getsockname()[1], "safe-probe", 1, True, second_auth, sdp), target)
            if code != 484:
                raise AssertionError(f"safe nonnumeric destination was not rejected: {code}")
            # A disabled gateway must release its SIP socket, block the voice
            # path and recover a fresh authenticated registrar on SIGHUP.
            original = open(config, encoding="utf-8").read()
            with open(config, "w", encoding="utf-8") as stream:
                stream.write(original.replace("role=SERVER", "role=DISABLED"))
            process.send_signal(signal.SIGHUP)
            def await_line(expected):
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    try:
                        line = lines.get(timeout=.2)
                    except queue.Empty:
                        continue
                    observed.append(line)
                    if line == expected:
                        return
                raise AssertionError("gateway event missing: " + expected)
            await_line("GATEWAY_RELOADED")
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                probe.bind(target)
            finally:
                probe.close()
            process.stdin.write("INCOMING\n")
            process.stdin.flush()
            await_line("HANGUP")
            with open(config, "w", encoding="utf-8") as stream:
                stream.write(original)
            process.send_signal(signal.SIGHUP)
            await_line("GATEWAY_RELOADED")
            register(second, host, target, "after-disabled")
        finally:
            first.close()
            second.close()
            invalid.close()
            process.stdin.write("QUIT\n")
            process.stdin.flush()
            process.wait(timeout=5)
            while not lines.empty():
                observed.append(lines.get())
        if any(line.startswith("DIAL ") for line in observed):
            raise AssertionError("isolated registrar test reached dial path")
        print(json.dumps({
            "backend": args.backend,
            "registered": True,
            "singleBindingReplacement": True,
            "authenticatedInvite": True,
            "invalidPasswordRejected": True,
            "replayRejected": True,
            "safeDestinationRejected": True,
            "disabledSocketClosed": True,
            "disabledIncomingBlocked": True,
            "registrarRecovered": True,
            "simCalls": False,
        }, sort_keys=True))


if __name__ == "__main__":
    main()
