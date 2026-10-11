/* ARM EABI, no libc, no audio opens, ioctls, AT commands or radio writes. */
static int call3(int n, int a, int b, int c) {
    register int r0 __asm__("r0") = a;
    register int r1 __asm__("r1") = b;
    register int r2 __asm__("r2") = c;
    register int r7 __asm__("r7") = n;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1), "r"(r2), "r"(r7) : "memory", "cc");
    return r0;
}
static void out(const char *s) {
    int len = 0;
    while (s[len]) ++len;
    while (len) {
        int done = call3(4, 1, (int)s, len);
        if (done <= 0) return;
        s += done; len -= done;
    }
}
static int run(void) {
    const char *paths[] = {"/dev/voice_device", "/dev/amr_device", "/dev/volte_device",
        "/dev/snd", "/dev/snd/controlC0", "/dev/slic-0", 0};
    int found = 0;
    out("MF79U custom firmware voice probe v0.2\nRead-only filesystem checks; no modem commands.\n");
    for (int i = 0; paths[i]; ++i) {
        int result = call3(33, (int)paths[i], 0, 0); /* access(F_OK) */
        out(paths[i]);
        if (result == 0) { ++found; out(": present\n"); }
        else if (result == -2) out(": absent\n");
        else out(": check failed\n");
    }
    out(found ? "Audio nodes present; call support still unverified.\n" :
        "No expected audio nodes. Voice backend unavailable via these interfaces.\n");
    const char *transport[] = {"/dev/rpm0", "/dev/rpm1", "/dev/rpm2", "/dev/rpm9", "/dev/at_ps", 0};
    out("CP transport nodes (presence only; no channel is opened):\n");
    for (int i = 0; transport[i]; ++i) {
        int result = call3(33, (int)transport[i], 0, 0);
        out(transport[i]);
        out(result == 0 ? ": present\n" : result == -2 ? ": absent\n" : ": check failed\n");
    }
    return found ? 0 : 2;
}
void _start(void) { int result = run(); call3(1, result, 0, 0); for (;;) {} }
