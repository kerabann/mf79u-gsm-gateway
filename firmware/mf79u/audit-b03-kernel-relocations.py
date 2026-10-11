#!/usr/bin/env python3
import argparse,json
from b03_kernel_relocations import audit_module
p=argparse.ArgumentParser(description='Reject direct Thumb branches into ARM B03 kernel exports')
p.add_argument('module');args=p.parse_args();r=audit_module(args.module);print(json.dumps(r,indent=2))
raise SystemExit(0 if r['safe'] else 1)
