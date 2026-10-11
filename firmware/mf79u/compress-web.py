#!/usr/bin/env python3
"""Precompress embedded public UI assets on the build host, not the modem."""
from pathlib import Path
import gzip
web=Path(__file__).resolve().parent/'control/web'
target=web/'compressed';target.mkdir(exist_ok=True)
for source in web.iterdir():
 if source.is_file():
  (target/(source.name+'.gz')).write_bytes(gzip.compress(source.read_bytes(),compresslevel=9,mtime=0))
