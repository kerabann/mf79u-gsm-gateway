#!/usr/bin/env python3
"""Isolated SIP MESSAGE fixture: fake local SMS service, no modem/radio access."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import socket
import struct
import subprocess
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("registrar", HERE / "test-sip-registrar.py")
registrar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registrar)


class SMSFixture:
    def __init__(self, path):
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(path)
        self.listener.listen()
        self.jobs = {}
        self.submitted = {}
        self.unconfirmed = False
        self.incoming_id = "0123456789abcdef" * 2
        self.number = b"+391234567"
        self.text = "Incoming Привет 🌍".encode()
        self.acked = False
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while True:
            try:
                c, _ = self.listener.accept()
                with c:
                    h = self.read(c, 9)
                    assert h[:4] == b"MSM1"
                    data = self.read(c, struct.unpack("!I", h[5:])[0])
                    status, out = 0, b""
                    if h[4] == 1:
                        id = data[:32].decode()
                        a, b = struct.unpack("!HH", data[32:36])
                        number, text = data[36:36+a].decode(), data[36+a:36+a+b].decode()
                        if len(text) > 670:
                            status = 1
                        elif id in self.jobs and self.jobs[id] != (number, text):
                            status = 4
                        else:
                            self.jobs[id] = (number, text)
                            self.submitted.setdefault(id, time.monotonic())
                    elif h[4] == 5:
                        id = data.decode()
                        status = 2 if id not in self.jobs else 5 if time.monotonic()-self.submitted[id] < 1 else 6 if self.unconfirmed else 0
                    elif h[4] == 2 and not self.acked:
                        number, text, date = self.number, self.text, b"2026-10-08T01:00:00+03:00"
                        out = self.incoming_id.encode() + struct.pack("!HHH", len(number), len(text), len(date)) + number + text + date
                    elif h[4] == 3:
                        self.acked = data.decode() == self.incoming_id
                    c.sendall(b"MSM1" + bytes([status]) + struct.pack("!I", len(out)) + out)
            except OSError:
                return

    @staticmethod
    def read(c, n):
        out = b""
        while len(out) < n:
            part = c.recv(n-len(out))
            if not part:
                raise OSError("short frame")
            out += part
        return out


def request(sock, target, host, uri, cid, seq, nonce, nc, text, mime="text/plain", password="local-lab-password"):
    auth = registrar.auth_header(password, "MESSAGE", uri, nonce, f"{nc:08x}") if nonce else ""
    raw = registrar.message("MESSAGE", uri, host, sock.getsockname()[1], cid, seq, authorization=auth, body=text)
    # Distinct SIP transport transactions exercise durable logical-SMS dedupe.
    raw = raw.replace(f"branch=z9hG4bK-{cid}-{seq};".encode(), f"branch=z9hG4bK-{cid}-{seq}-{nc};".encode())
    raw = raw.replace(b"Content-Type: application/sdp", ("Content-Type: " + mime).encode())
    return registrar.final_reply(sock, raw, target)[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway", required=True)
    args = parser.parse_args()
    host = socket.gethostbyname(socket.gethostname())
    target = (host, 15080)
    with tempfile.TemporaryDirectory(prefix="mf79u-sms-fixture-") as directory:
        ipc = os.path.join(directory, "sms.sock")
        fixture = SMSFixture(ipc)
        cfg = Path(directory) / "gateway.ini"
        cfg.write_text("role=SERVER\nextension=100\nextension_password=local-lab-password\n"
                       "server=127.0.0.1\nport=5060\ntransport=UDP\nusername=mf79u\npassword=\nrealm=*\n"
                       "register=0\nincoming_user=mf79u\nlocal_port=15080\n" + f"bind={host}\n"
                       "trusted_peers=127.0.0.1\ncodecs=OPUS,G722,PCMA,PCMU,G729\nca_file=\nvoice_mode=CS\n")
        env = dict(os.environ, MF79U_SMS_SOCKET=ipc)
        proc = subprocess.Popen([args.gateway, "--wideband", "--config", str(cfg)], env=env,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        output, lines = [], queue.Queue()
        def reader():
            for line in proc.stdout:
                output.append(line.strip())
                lines.put(line.strip())
        threading.Thread(target=reader, daemon=True).start()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((host, 0)); sock.settimeout(4)
        stranger = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        stranger.bind((host, 0)); stranger.settimeout(4)
        try:
            deadline = time.monotonic() + 8
            while lines.get(timeout=8) != "GATEWAY_LISTENING":
                if time.monotonic() > deadline:
                    raise AssertionError("startup")
            # No READY: MESSAGE and client registration must work without IMS.
            proc.stdin.write("NOT_READY\n"); proc.stdin.flush()
            nonce = registrar.register(sock, host, target, "sms-binding")
            # The sender URI must identify the SIM sender, not the SIP account.
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                incoming, _ = sock.recvfrom(8192)
                if incoming.startswith(b"MESSAGE "):
                    break
            else:
                raise AssertionError("incoming SMS not delivered")
            assert "Incoming Привет 🌍".encode() in incoming
            assert re.search(br"(?im)^From:.*sip:\+391234567@", incoming)
            assert b"Content-Type: text/plain" in incoming
            headers = [b"SIP/2.0 200 OK"]
            for name in (b"Via", b"From", b"To", b"Call-ID", b"CSeq"):
                found = re.search(br"(?im)^"+name+br":\s*([^\r\n]+)", incoming)
                value = found.group(1)
                if name == b"To": value += b";tag=fixture"
                headers.append(name + b": " + value)
            sock.sendto(b"\r\n".join(headers+[b"Content-Length: 0", b"", b""]), target)
            end = time.monotonic()+3
            while not fixture.acked and time.monotonic()<end: time.sleep(.05)
            assert fixture.acked, "incoming delivery was not acknowledged"

            # Service status must be a separate MF79U conversation, never a
            # message impersonating the cellular recipient.
            fixture.incoming_id = "fedcba9876543210" * 2
            fixture.number, fixture.text = b"MF79U", b"MF79U status: modem API confirmation unavailable"
            fixture.acked = False
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                notice, _ = sock.recvfrom(8192)
                if notice.startswith(b"MESSAGE "):
                    break
            else:
                raise AssertionError("service notice not delivered")
            assert re.search(br"(?im)^From:.*sip:MF79U@", notice)
            assert fixture.text in notice
            headers = [b"SIP/2.0 200 OK"]
            for name in (b"Via", b"From", b"To", b"Call-ID", b"CSeq"):
                value = re.search(br"(?im)^"+name+br":\s*([^\r\n]+)", notice).group(1)
                if name == b"To": value += b";tag=fixture"
                headers.append(name + b": " + value)
            sock.sendto(b"\r\n".join(headers+[b"Content-Length: 0", b"", b""]), target)
            end = time.monotonic()+3
            while not fixture.acked and time.monotonic()<end: time.sleep(.05)
            assert fixture.acked, "service notice was not acknowledged"

            # A numeric voice INVITE remains unavailable without IMS. No DIAL.
            voice_uri = f"sip:1234567@{host}:15080"
            voice_auth = registrar.auth_header("local-lab-password", "INVITE", voice_uri, nonce, "00000002")
            voice = registrar.message("INVITE", voice_uri, host, sock.getsockname()[1], "no-ims-voice", 1, authorization=voice_auth)
            assert registrar.final_reply(sock, voice, target)[0] == 503
            assert not any(line.startswith("DIAL ") for line in output)
            # Keep increasing nonce-count after the authenticated INVITE.
            nonce = registrar.register(sock, host, target, "sms-rebinding")
            uri = f"sip:+391234567@{host}:15080"
            assert request(sock,target,host,uri,"text",1,nonce,2,"Outgoing Привет 🌍") == 200
            # New SIP transaction, same Call-ID/CSeq: same logical SMS, no duplicate.
            assert request(sock,target,host,uri,"text",1,nonce,3,"Outgoing Привет 🌍") == 200
            assert len(fixture.jobs) == 1
            fixture.unconfirmed = True
            assert request(sock,target,host,uri,"unconfirmed",1,nonce,12,"ambiguous") == 504
            fixture.unconfirmed = False
            nonce = registrar.register(sock, host, target, "after-uncertain")
            assert request(sock,target,host,uri,"text",1,nonce,4,"changed") == 409
            cpim = "From: <sip:fake@example.org>\r\nTo: <sip:wrong@example.org>\r\n\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nCPIM Привет"
            assert request(sock,target,host,uri,"cpim",1,nonce,5,cpim,"message/cpim") == 200
            assert any(number=="+391234567" and text=="CPIM Привет" for number,text in fixture.jobs.values())
            count = len(fixture.jobs)
            assert request(sock,target,host,uri,"receipt",1,nonce,6,"<imdn/>","application/imdn+xml") == 200
            assert request(sock,target,host,uri,"typing",1,nonce,7,"<isComposing/>","application/im-iscomposing+xml") == 200
            assert len(fixture.jobs) == count
            time.sleep(1.1)  # Respect the intentional bounded per-second request budget.
            assert request(sock,target,host,uri,"encrypted",1,nonce,8,"ciphertext","application/lime") == 415
            assert request(sock,target,host,f"sip:probe@{host}:15080","bad-number",1,nonce,9,"text") == 484
            assert request(sock,target,host,uri,"too-long",1,nonce,10,"x"*671) == 400
            assert request(sock,target,host,uri,"wrong-password",1,nonce,11,"text",password="incorrect") == 403
            assert request(stranger,target,host,uri,"no-auth",1,"",0,"text") == 401
            _, other_nonce = registrar.challenge(stranger,host,target,"unregistered")
            assert request(stranger,target,host,uri,"unregistered-message",1,other_nonce,1,"text") == 480
            assert not any(line.startswith("DIAL ") for line in output)
            print(json.dumps({"incomingUnicode":True,"senderURI":True,"deliveryAck":True,"outgoingUnicode":True,
                              "submissionConfirmed200":True,"unconfirmed504":True,"cpim":True,"idempotency":True,"payloadConflictRejected":True,"typingReceiptsNotSMS":True,
                              "authentication":True,"registrationRequired":True,"invalidDestinationRejected":True,
                              "unsupportedEncryptionRejected":True,"serviceNoticeSender":True,
                              "smsMutations":False,"simCalls":False,"smsWithoutIMS":True,"voiceWithoutIMSRejected":True},sort_keys=True))
        finally:
            sock.close(); stranger.close(); fixture.listener.close()
            proc.stdin.write("QUIT\n"); proc.stdin.flush(); proc.wait(timeout=5)


if __name__ == "__main__":
    main()
