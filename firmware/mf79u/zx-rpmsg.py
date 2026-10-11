#!/usr/bin/env python3
"""Offline ZX29 ring snapshot decoder; never opens a modem or physical memory.

Framing reference: drivers/rpmsg/zx29_smd.c, Stefan Dösinger's dlink branch.
Applicability to B03 voice payloads is unverified; no channel IDs are assumed.
"""
import argparse
import json
from pathlib import Path
import struct

MAGIC = 0x5453

def decode(ring, send_pos, recv_pos):
    size = len(ring)
    if size < 8 or size % 4 or not (0 <= send_pos < size and 0 <= recv_pos < size):
        raise ValueError('Invalid ring size or cursor')
    if send_pos % 4 or recv_pos % 4:
        raise ValueError('Cursors must be aligned to four bytes')
    count = (send_pos - recv_pos) % size
    data = bytes(ring[(recv_pos+i) % size] for i in range(count))
    packets = []
    cursor = 0
    while cursor < count:
        if count-cursor < 4:
            raise ValueError('Truncated frame header')
        magic, length = struct.unpack_from('<HH', data, cursor)
        if magic != MAGIC:
            raise ValueError(f'Bad magic at stream offset {cursor}')
        total = 4 + ((length+3) & ~3)
        if total > count-cursor:
            raise ValueError(f'Incomplete frame at stream offset {cursor}')
        packets.append({'ring_offset': (recv_pos+cursor) % size,
                        'length': length, 'payload_hex': data[cursor+4:cursor+4+length].hex()})
        cursor += total
    return packets

def selftest():
    # Independently hand-specified wire frames: zero-length, 3-byte, wraparound.
    assert decode(bytes.fromhex('53540000000000000000000000000000'), 4, 0) == [
        {'ring_offset': 0, 'length': 0, 'payload_hex': ''}]
    ring = bytearray(32)
    wire = bytes.fromhex('53540300616263ff53540000')
    for index, byte in enumerate(wire):
        ring[(28+index) % 32] = byte
    assert decode(ring, 8, 28) == [
        {'ring_offset': 28, 'length': 3, 'payload_hex': '616263'},
        {'ring_offset': 4, 'length': 0, 'payload_hex': ''}]
    assert decode(ring, 8, 8) == []
    for buffer, send, recv in ((bytes.fromhex('00000300616263ff0000000000000000'), 8, 0),
                              (bytes.fromhex('53540d00000000000000000000000000'), 8, 0),
                              (bytes(16), 17, 0), (bytes(16), 3, 0)):
        try:
            decode(buffer, send, recv)
        except ValueError:
            continue
        raise AssertionError('Malformed input was accepted')
    print('PASS: zero length, wraparound, padding, empty ring and malformed frames')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--ring', type=Path)
    parser.add_argument('--send-pos', type=int)
    parser.add_argument('--recv-pos', type=int)
    args = parser.parse_args()
    if args.selftest:
        selftest()
    elif args.ring is not None and args.send_pos is not None and args.recv_pos is not None:
        print(json.dumps(decode(args.ring.read_bytes(), args.send_pos, args.recv_pos), indent=2))
    else:
        parser.error('Provide --selftest or --ring, --send-pos and --recv-pos')
