"""Bounded, metadata-only live kernel failure capture over the existing ADB.

Consumes /proc/kmsg without clearing dmesg or changing kernel panic policy.
No packet, speech, memory dump or unrelated kernel message is saved.
"""
import json,re,subprocess,threading,time

class KernelCapture:
    def __init__(self,radio,path):
        self.radio=radio;self.path=path;self.process=None;self.thread=None
        self.pidfile='/dev/.mf79u-cs-kmsg.pid'
        self.result={'filter_version':3,'device_policy_changed':False,'raw_kernel_log_saved':False,'messages':[]}

    @staticmethod
    def allowed(line):
        prefix=re.match(r'^(?:<\d+>)?\[\s*([0-9.]+)\]\s*(.*)$',line)
        if not prefix:return None
        text=prefix[2]
        if (text.startswith(('MF79U_CS_MO ','MF79U_CS_ASC ','MF79U_CS_PCM ','MF79U_CS_I2S_DSP_LOOP ',
                            'Kernel panic -','Oops:','Internal error:',
                            'Unable to handle kernel','Out of memory',
                            '[zx297510]Out of memory','User ramdump ',
                            'Ramdump info:','PC is at ','LR is at ','pc :','sp :','Backtrace:',
                            'trans server received forced dump request from ',
                            'trans server received force dump request from ',
                            'AP server breakdown happens','AP server recv error icp msg',
                            '[ramdump] icpmsg send fail','[ZXIC]ramdump forced panic',
                            'dump at user, app name is:','dump at kernel, app name is:',
                            'slob: double free error!','Fatal exception',
                            'RT Watchdog Timeout:','Watchdog timer expire',
                            '[zx soft wdt]:'))
            or re.match(r'^\S+ invoked oom-killer: gfp_mask=',text)
            or re.match(r'^\[<[0-9a-f]{8}>\]',text)):
            return float(prefix[1]),line[:700]
        return None

    def save(self):
        self.path.write_text(json.dumps(self.result,indent=2)+'\n');self.path.chmod(0o600)

    def read(self):
        for raw in self.process.stdout:
            match=self.allowed(raw.decode(errors='replace').strip())
            if match and match[0]>=self.since:
                self.result['messages'].append(match[1])
                self.result['messages']=self.result['messages'][-512:];self.save()
        self.result['stream_eof']=True;self.save()

    def start(self):
        if self.radio.shell('test -e '+self.pidfile+' && echo PRESENT')=='PRESENT':
            raise RuntimeError('Kernel capture already owned')
        self.result['boot_id']=self.radio.shell('cat /proc/sys/kernel/random/boot_id')
        self.since=float(self.radio.shell('cat /proc/uptime').split()[0])
        self.result['start_uptime']=self.since;self.save()
        command='umask 077; echo $$ > '+self.pidfile+'; exec /mnt/userdata/mf79u/tools/busybox cat /proc/kmsg'
        self.process=subprocess.Popen([self.radio.ADB,'shell',command],stdin=subprocess.DEVNULL,
                                      stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        self.thread=threading.Thread(target=self.read,daemon=True);self.thread.start()
        time.sleep(.3)
        if self.process.poll() is not None:raise RuntimeError('Kernel capture exited at startup')

    def close(self):
        try:
            if self.radio.shell('cat /proc/sys/kernel/random/boot_id')!=self.result.get('boot_id'):
                self.result['new_boot']=True;self.result['closed']=True;self.save();return self.result
            if self.process and self.process.poll() is None:
                pid=self.radio.shell('cat '+self.pidfile)
                if not pid.isdigit():raise RuntimeError('Invalid kernel capture owner')
                command=self.radio.shell('cat /proc/'+pid+'/cmdline').replace('\x00',' ')
                if not command.endswith('busybox cat /proc/kmsg '):raise RuntimeError('Kernel capture owner changed')
                self.radio.shell('kill -TERM '+pid)
                self.process.wait(timeout=5)
            if self.thread:self.thread.join(timeout=5)
            self.radio.shell('rm -f '+self.pidfile)
            self.result['closed']=True
        except Exception as error:
            self.result['cleanup_error']=type(error).__name__
        self.save();return self.result
