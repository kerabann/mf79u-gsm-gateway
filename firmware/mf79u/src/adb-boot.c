/* B03 USB boot policy. Only usb_modetype in NV_RO is writable here.
 * The stock nv CLI's getro and libnvram disassembly identify NV_RO as "ro".
 * No reset, USB re-enumeration or factory/AMT transition is performed. */
#include <stdio.h>
#include <string.h>
#include <unistd.h>

extern int nv_get_item(const char *, const char *, char *, int);
extern int nv_set_item(const char *, const char *, const char *, int);
extern int nv_commit(const char *);

int main(int argc, char **argv) {
    if (argc != 2 || (strcmp(argv[1], "--check") && strcmp(argv[1], "--ensure"))) return 2;
    alarm(5); /* Do not indefinitely hold the boot script on an unavailable NV service. */
    char mode[32] = {0};
    if (nv_get_item("ro", "usb_modetype", mode, sizeof(mode))) return 3;
    if (!strcmp(mode, "debug")) { puts("ADB_PROFILE_DEBUG_UNCHANGED"); return 0; }
    if (!strcmp(argv[1], "--check")) { puts("ADB_PROFILE_NOT_DEBUG"); return 4; }
    /* Retain explicitly selected recovery profiles and refuse unknown values. */
    if (*mode && strcmp(mode, "user")) { puts("ADB_PROFILE_RESERVED_UNCHANGED"); return 5; }
    if (nv_set_item("ro", "usb_modetype", "debug", 1)) return 6;
    if (nv_commit("ro")) return 7;
    memset(mode, 0, sizeof(mode));
    if (nv_get_item("ro", "usb_modetype", mode, sizeof(mode)) || strcmp(mode, "debug")) return 8;
    puts("ADB_PROFILE_DEBUG_APPLIED");
    return 0;
}

#ifndef MF79U_ADB_BOOT_HOST_TEST
extern void __uClibc_main(int(*)(int,char**),int,char**,void*,void*,void*,void*);
__attribute__((naked,noreturn)) void _start(void) {
    __asm__ volatile("ldr r1, [sp], #4\nmov r2, sp\nmov r4, sp\nldr r0, =main\nmov r3, #0\n"
                     "bic sp, sp, #7\nsub sp, sp, #16\nstr r3, [sp]\nstr r3, [sp, #4]\nstr r4, [sp, #8]\n"
                     "bl __uClibc_main\nmov r0, #1\nmov r7, #1\nsvc #0\n");
}
#endif
