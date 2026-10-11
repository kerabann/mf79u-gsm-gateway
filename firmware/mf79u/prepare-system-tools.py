#!/usr/bin/env python3
"""Prepare checksum-pinned official sources, with a private SSH credential store."""
from pathlib import Path
import hashlib, tarfile, difflib
ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/'work/zte/system-tools'
SOURCES={'dropbear-2026.94.tar.bz2':'e098034a843699200c8c977a991fff73159735bf795d5f72ef672c41a6b1ae81','busybox-1.37.0.tar.bz2':None}
SOURCES['busybox-1.37.0.tar.bz2']='3311dff32e746499f4df0d5df04d7eb396382d7e108bb9250e7b519b837043a4'
for name,checksum in SOURCES.items():
 assert hashlib.sha256((TOOLS/name).read_bytes()).hexdigest()==checksum
 with tarfile.open(TOOLS/name) as t:t.extractall(TOOLS,filter='data')
p=TOOLS/'dropbear-2026.94/src/common-session.c'; old=p.read_text();new=old
needle='\tpw = getpwnam(username);'
new=new.replace(needle,'''\t/* MF79U has one existing UID-0 account; do not modify vendor passwd/shadow. */
\tif (IS_DROPBEAR_SERVER && strcmp(username, "admin") != 0) return;
'''+needle)
needle='\t\tses.authstate.pw_passwd = m_strdup(passwd_crypt);'
new=new.replace(needle,'''\t\tif (IS_DROPBEAR_SERVER) {
\t\t\tchar hash[256]; struct stat st;
\t\t\tint fd = open("/mnt/userdata/mf79u/ssh.password", O_RDONLY | O_NOFOLLOW);
\t\t\tssize_t n = -1;
\t\t\tif (fd >= 0 && fstat(fd, &st) == 0 && S_ISREG(st.st_mode) && st.st_uid == 0 && (st.st_mode & 077) == 0)
\t\t\t\tn = read(fd, hash, sizeof(hash)-1);
\t\t\tif (fd >= 0) close(fd);
\t\t\tif (n > 0) { hash[n] = 0; hash[strcspn(hash, "\\r\\n")] = 0; }
\t\t\tpasswd_crypt = n > 0 && !strncmp(hash, "$6$", 3) && strlen(hash) >= 90 ? hash : "!!";
\t\t\tses.authstate.pw_passwd = m_strdup(passwd_crypt);
\t\t\tm_burn(hash, sizeof(hash));
\t\t} else {
'''+needle+'''\n\t\t}''')
new=new.replace('const char* get_user_shell() {','''const char* get_user_shell() {
\tif (IS_DROPBEAR_SERVER) return "/mnt/userdata/mf79u/tools/ssh-shell";''')
p.write_text(new)
(ROOT/'firmware/mf79u/src/dropbear-mf79u.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/src/common-session.c',tofile='b/src/common-session.c')))
(TOOLS/'dropbear-2026.94/localoptions.h').write_text('''#define DROPBEAR_SK_KEYS 0
#define DROPBEAR_SVR_PUBKEY_AUTH 0
#define DROPBEAR_SVR_PUBKEY_OPTIONS 0
#define DROPBEAR_SVR_AGENTFWD 0
#define DROPBEAR_SVR_LOCALTCPFWD 0
#define DROPBEAR_SVR_REMOTETCPFWD 0
#define DROPBEAR_SFTPSERVER 0
#define DEFAULT_PATH "/mnt/userdata/mf79u/tools/bin:/usr/bin:/bin:/usr/sbin:/sbin"
''')
(ROOT/'firmware/mf79u/build/system-tools-sources.json').write_text(__import__('json').dumps(SOURCES,indent=2)+'\n')
