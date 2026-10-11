"""DHCP DISCOVER only: inspect OFFER, never accept a lease or change host routes."""
import ipaddress,json,os,socket,struct,time

def probe(server='192.168.0.1'):
 xid=int.from_bytes(os.urandom(4),'big');mac=b'\x02\x00\x79'+os.urandom(3)
 packet=struct.pack('!BBBBIHH4s4s4s4s16s64s128s',1,1,6,0,xid,0,0x8000,b'\0'*4,b'\0'*4,b'\0'*4,b'\0'*4,mac+b'\0'*10,b'\0'*64,b'\0'*128)+b'\x63\x82\x53\x63'+b'\x35\x01\x01'+b'\x37\x05\x01\x03\x06\x79\xf9'+b'\xff'
 with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
  sock.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1);sock.bind(('0.0.0.0',68));sock.settimeout(4)
  for attempt in range(3):
   sock.sendto(packet,(server,67))
   deadline=time.monotonic()+4
   while time.monotonic()<deadline:
    try:data,_=sock.recvfrom(4096)
    except socket.timeout:break
    if len(data)<240 or struct.unpack_from('!I',data,4)[0]!=xid:continue
    opts={};i=240
    while i<len(data):
     code=data[i];i+=1
     if code==255:break
     if code==0:continue
     size=data[i];i+=1;opts[code]=opts.get(code,b'')+data[i:i+size];i+=size
    if opts.get(53)!=b'\x02':continue
    addresses=lambda code:[str(ipaddress.IPv4Address(opts[code][i:i+4])) for i in range(0,len(opts.get(code,b'')),4)]
    routes=[];value=opts.get(121,b'');i=0
    while i<len(value):
     width=value[i];i+=1;count=(width+7)//8;dest=value[i:i+count]+b'\0'*(4-count);i+=count;gw=value[i:i+4];i+=4
     routes.append({'destination':str(ipaddress.IPv4Address(dest))+'/'+str(width),'gateway':str(ipaddress.IPv4Address(gw))})
    return {'offeredAddress':str(ipaddress.IPv4Address(data[16:20])),'subnetMask':addresses(1),'gateway':addresses(3),'dns':addresses(6),'routes121':routes,'option249Matches121':121 in opts and opts.get(249)==opts[121]}
 raise RuntimeError('No DHCP OFFER')
if __name__=='__main__':print(json.dumps(probe(),indent=2))
