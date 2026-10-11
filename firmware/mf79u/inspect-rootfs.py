#!/usr/bin/env python3
"""Validate JFFS2 contents against an extracted tree; retain modes in devtable."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
from jefferson import jffs2 as j

def inspect(image, root):
    j.set_endianness('<')
    fs = j.scan_fs(image.read_bytes(), '<')
    nodes = fs[j.JFFS2_NODETYPE_INODE]
    entries = fs[j.JFFS2_NODETYPE_DIRENT]
    if any(not n.node_crc_match or not n.data_crc_match
           for fragments in nodes.values() for n in fragments):
        raise ValueError('Invalid inode or data CRC')
    if any(d.ino == 0 for d in entries.values()):
        raise ValueError('Deleted-dirent history needs a more complete JFFS2 replay')
    def name(ino, visited=None):
        visited = set() if visited is None else visited
        if ino == 1:
            return ''
        if ino in visited or ino not in entries:
            raise ValueError('Cyclic or missing directory parent')
        visited.add(ino)
        d = entries[ino]
        leaf = d.name.decode()
        if leaf in ('', '.', '..') or '/' in leaf:
            raise ValueError('Unsafe directory name')
        return '/'.join(p for p in (name(d.pino, visited), leaf) if p)
    # mkfs.jffs2 handles the implicit root; a '/' devtable entry is rejected.
    table = []
    records = []
    for ino, d in entries.items():
        rel = name(ino)
        path = root / rel
        pieces = sorted(nodes[ino], key=lambda n: n.version)
        latest = pieces[-1]
        mode = stat.S_IMODE(latest.mode)
        if stat.S_ISREG(latest.mode):
            data = bytearray(latest.isize)
            for n in pieces:
                end = min(n.offset + len(n.data), latest.isize)
                if end > n.offset:
                    data[n.offset:end] = n.data[:end-n.offset]
            if path.is_symlink() or path.read_bytes() != data:
                raise ValueError('File differs: ' + rel)
            kind = 'f'
            sha = hashlib.sha256(data).hexdigest()
        elif stat.S_ISDIR(latest.mode):
            if path.is_symlink() or not path.is_dir():
                raise ValueError('Directory differs: ' + rel)
            kind, sha = 'd', None
        elif stat.S_ISLNK(latest.mode):
            if not path.is_symlink() or str(path.readlink()).encode() != latest.data:
                raise ValueError('Symlink differs: ' + rel)
            kind, sha = 'l', None
        else:
            raise ValueError('Unsupported inode type: ' + rel)
        if (latest.uid, latest.gid) != (0, 0):
            raise ValueError('Non-root ownership requires explicit handling')
        if kind != 'l':
            table.append(f'/{rel} {kind} {mode:o} {latest.uid} {latest.gid} - - - - -')
        records.append({'path': '/' + rel, 'kind': kind, 'mode': oct(mode), 'sha256': sha})
    print(f'Validated {len(records)} paths, file contents, symlinks and inode/data CRCs')
    return table, records

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('image', type=Path)
    parser.add_argument('tree', type=Path)
    parser.add_argument('--device-table', type=Path)
    parser.add_argument('--inventory', type=Path)
    args = parser.parse_args()
    table, records = inspect(args.image, args.tree)
    if args.device_table:
        args.device_table.write_text('\n'.join(table) + '\n')
    if args.inventory:
        args.inventory.write_text(json.dumps(records, indent=2) + '\n')
