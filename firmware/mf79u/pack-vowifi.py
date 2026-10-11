#!/usr/bin/env python3
"""Package verified ARM clients; certificates are public, identities stay on SIM."""
from pathlib import Path
import hashlib,io,json,tarfile
root=Path(__file__).resolve().parent
b=root/'build';bundle=b/'vowifi-runtime.tar.xz'
certs={} # Current mutual EAP-only profile requires no public-key CA store.
artifacts={n:(b/('mf79u-vowifi-'+n)).read_bytes() for n in ['charon','swanctl','prepare']}
next_bundle=bundle.with_suffix('.next')
with tarfile.open(next_bundle,'w:xz',preset=3) as t:
 for name,data in {**{'.mf79u-vowifi-'+n:v for n,v in artifacts.items()},**certs}.items():
  info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o700 if name.startswith('.') else 0o600;t.addfile(info,io.BytesIO(data))
next_bundle.replace(bundle)
(b/'vowifi-runtime-build.json').write_text(json.dumps(dict(date='2026-10-11',artifacts={n:hashlib.sha256(d).hexdigest() for n,d in artifacts.items()},caCertificates=len(certs),bundleSHA256=hashlib.sha256(bundle.read_bytes()).hexdigest()),indent=2)+'\n')
print('VoWiFi bundle:',bundle.stat().st_size,'bytes')
