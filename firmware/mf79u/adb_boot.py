"""Shared, idempotent B03 rc transformation for installed and packaged firmware."""
START = b'# MF79U automatic ADB boot policy v1\n'
END = b'# End MF79U automatic ADB boot policy\n'
BLOCK = (START +
    b'if [ "$bootmode" != "amt" ] && [ "$bootreason" != "10" ]; then\n'
    b' /usr/zte/mf79u/adb-boot --ensure >/dev/.mf79u-adb-boot.log 2>&1\n'
    b'fi\n' + END)
ANCHOR = b'adbd &\nif [[ $bootmode == "amt" ]]; then\n'


def patch_rc(data):
    if START in data:
        if data.count(BLOCK) != 1 or data.count(START) != 1:
            raise ValueError('Existing ADB boot policy differs')
        if BLOCK + ANCHOR not in data:
            raise ValueError('ADB policy is outside the pre-USB startup location')
        return data
    if END in data or data.count(ANCHOR) != 1:
        raise ValueError('Unexpected B03 ADB startup anchor')
    result = data.replace(ANCHOR, BLOCK + ANCHOR, 1)
    if result.index(BLOCK) > result.index(b'zte_usb_cfg &\n'):
        raise ValueError('ADB profile must be selected before USB configuration')
    return result


def unpatch_rc(data):
    patch_rc(data)  # Validate the installed block before removing anything.
    return data.replace(BLOCK, b'', 1)
