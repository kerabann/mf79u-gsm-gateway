#!/usr/bin/env python3
"""Recover the B03 factory AT interfaces from PID1405 on macOS.

No partition image or SD file is written. B03's vendor OPENDL command changes
the boot flag and USB mode; the next step must restore debug mode through AT.
This is a manual recovery helper, not a boot service or firmware installer.
"""
import argparse
import ctypes as c
import os
import plistlib
import struct
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--switch-factory', action='store_true', required=True)
parser.parse_args()
raise SystemExit("Disabled: userdata runtime was absent after factory-mode recovery; audit the B03 reset path before reuse.")
if sys.platform != 'darwin' or os.geteuid() != 0:
    raise SystemExit('Run this helper on macOS with sudo in your own terminal.')

# Flush only the two known modem volumes. Refuse a non-USB or renamed volume.
volumes = []
for path in ['/Volumes/ZTEMODEM', '/Volumes/ZTE_SD']:
    if not os.path.ismount(path):
        continue
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', path]))
    if info.get('BusProtocol') != 'USB':
        raise SystemExit('Unexpected volume protocol; no USB command sent.')
    disk = info['ParentWholeDisk']
    if not disk.startswith('disk') or not disk[4:].isdigit():
        raise SystemExit('Unexpected disk identifier; no USB command sent.')
    volumes.append(disk)

u = c.CDLL('/opt/homebrew/lib/libusb-1.0.dylib')
u.libusb_init.argtypes = [c.POINTER(c.c_void_p)]
u.libusb_open_device_with_vid_pid.argtypes = [c.c_void_p, c.c_ushort, c.c_ushort]
u.libusb_open_device_with_vid_pid.restype = c.c_void_p
u.libusb_set_auto_detach_kernel_driver.argtypes = [c.c_void_p, c.c_int]
u.libusb_claim_interface.argtypes = [c.c_void_p, c.c_int]
u.libusb_release_interface.argtypes = [c.c_void_p, c.c_int]
u.libusb_bulk_transfer.argtypes = [c.c_void_p, c.c_ubyte, c.c_void_p, c.c_int,
                                 c.POINTER(c.c_int), c.c_uint]
u.libusb_close.argtypes = [c.c_void_p]
u.libusb_exit.argtypes = [c.c_void_p]
ctx = c.c_void_p()
if u.libusb_init(c.byref(ctx)):
    raise SystemExit('libusb initialization failed.')
handle = None
claimed = False
sent = False
unmounted = []
try:
    handle = u.libusb_open_device_with_vid_pid(ctx, 0x19d2, 0x1405)
    if not handle:
        raise SystemExit('Expected MF79U PID1405 not found; no command sent.')
    for disk in dict.fromkeys(volumes):
        subprocess.run(['diskutil', 'unmountDisk', '/dev/' + disk], check=True)
        unmounted.append(disk)
    detach = u.libusb_set_auto_detach_kernel_driver(handle, 1)
    if detach not in (0, -12):  # NOT_SUPPORTED permits an ordinary claim.
        raise SystemExit('USB driver capture failed: ' + str(detach))
    rc = u.libusb_claim_interface(handle, 2)
    if rc:
        raise SystemExit('USB interface access failed: ' + str(rc) + '; no command sent.')
    claimed = True
    # PID1405 interface2 bulk endpoints02/82 were inspected on the actual modem.
    # Six-byte vendor OPENDL CDB, no data phase, CD-ROM LUN0, never WRITE/FORMAT.
    cbw = struct.pack('<IIIBBB', 0x43425355, 0x4d463739, 0, 0, 0, 6)
    cbw += bytes([0x99]) + bytes(15)
    assert len(cbw) == 31
    buf = c.create_string_buffer(cbw)
    transferred = c.c_int()
    rc = u.libusb_bulk_transfer(handle, 0x02, buf, 31, c.byref(transferred), 1500)
    sent = transferred.value == 31
    if not sent:
        raise SystemExit('USB command was not fully sent: ' + str(rc))
    print('Factory AT interface request sent. Re-enumeration and AT must be verified.')
finally:
    if handle:
        if claimed:
            u.libusb_release_interface(handle, 2)
        u.libusb_close(handle)
    u.libusb_exit(ctx)
    if not sent:
        for disk in unmounted:
            subprocess.run(['diskutil', 'mountDisk', '/dev/' + disk], check=False)
