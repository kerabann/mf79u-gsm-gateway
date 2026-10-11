/* Remove only queues inventoried as newly created by our stopped RAM test. */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <sys/msg.h>
int main(int argc,char **argv) {
    if (argc!=5) return 2;
    int id=(int)strtol(argv[1],NULL,10);
    int32_t key=(int32_t)strtol(argv[2],NULL,10);
    long stamp=strtol(argv[3],NULL,10),pid=strtol(argv[4],NULL,10);
    if (key!=5181 && key!=-2130378751 && key!=0 && key!=0x701e && key!=0x700f) return 2;
    struct msqid_ds ds;
    if (msgctl(id,IPC_STAT,&ds)) {
        if (errno==EINVAL || errno==EIDRM) { puts("already absent"); return 0; }
        perror("stat own queue"); return 1;
    }
    if ((int32_t)ds.msg_perm.__key!=key || (long)ds.msg_ctime!=stamp ||
        ds.msg_perm.uid!=0 || ds.msg_perm.cuid!=0) {
        fprintf(stderr,"Queue identity/owner mismatch; refused\n"); return 1;
    }
    /* Old kernels may report the IPC worker TID rather than the process PID. */
    pid_t users[]={ds.msg_lspid,ds.msg_lrpid};
    for (unsigned i=0;i<2;++i) if (users[i] && users[i]!=pid) {
        errno=0;
        if (!kill(users[i],0) || errno!=ESRCH) {
            fprintf(stderr,"Queue still has a live foreign user; refused\n"); return 1;
        }
    }
    if (msgctl(id,IPC_RMID,NULL)) { perror("remove own queue"); return 1; }
    printf("removed own queue id=%d key=%d\n",id,key); return 0;
}
