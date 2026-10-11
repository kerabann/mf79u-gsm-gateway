#define _FILE_OFFSET_BITS 64
#include <fcntl.h>
#include <linux/fs.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>

/* Re-read the partition map after Mac formatting. No block writes. */
int main(void) {
    char line[1024];
    FILE *f = fopen("/sys/devices/platform/zx29_hsotg.0/gadget/lun1/file", "r");
    if (!f) { perror("LUN status"); return 1; }
    if (fgets(line,sizeof(line),f) && strspn(line,"\r\n") != strlen(line)) {
        fputs("Refusing: card is still exported over USB\n",stderr);fclose(f);return 1;
    }
    fclose(f);
    f=fopen("/proc/mounts","r");
    if (!f) return 1;
    while (fgets(line,sizeof(line),f)) {
        if (strstr(line,"/dev/mmcblk0")) {
            fputs("Refusing: card is mounted\n",stderr);fclose(f);return 1;
        }
    }
    fclose(f);
    int fd=open("/dev/mmcblk0",O_RDONLY|O_CLOEXEC);
    if (fd<0) {perror("card");return 1;}
    struct stat st;uint64_t size=0;
    if (fstat(fd,&st) || !S_ISBLK(st.st_mode) || major(st.st_rdev)!=179
            || minor(st.st_rdev)!=0 || ioctl(fd,BLKGETSIZE64,&size)
            || size!=UINT64_C(31268536320)) {
        fputs("Refusing: unexpected card device or size\n",stderr);close(fd);return 1;
    }
    if (ioctl(fd,BLKRRPART)) {perror("BLKRRPART");close(fd);return 1;}
    close(fd);puts("SD_PARTITION_REREAD_OK");return 0;
}
