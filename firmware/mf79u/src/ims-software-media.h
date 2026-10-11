#ifndef MF79U_SOFTWARE_MEDIA_H
#define MF79U_SOFTWARE_MEDIA_H
#include <stddef.h>
#include <sys/types.h>
void mf79u_media_enable(void);
int mf79u_media_path(const char *path);
int mf79u_media_register(int fd,int kind);
int mf79u_media_kind(int fd);
void mf79u_media_close(int fd);
int mf79u_media_ioctl(int fd,unsigned long request,void *argument);
ssize_t mf79u_media_read(int fd,void *buffer,size_t size);
ssize_t mf79u_media_write(int fd,const void *buffer,size_t size);
int mf79u_media_preopen(const void *config);
int mf79u_media_resource(const void *request,void *response);
#endif
