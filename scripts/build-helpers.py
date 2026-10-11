from pathlib import Path
import subprocess
root = Path(__file__).resolve().parents[1]
commands = []
for name in ['detach-control', 'detach-native', 'detach-led']:
    commands.append('arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a -mfloat-abi=soft firmware/mf79u/profiles/b03/' + name + '.c -o firmware/mf79u/build/' + name)
for name in ['ram-http-get', 'sd-reread', 'sd-backup-server']:
    commands.append('arm-linux-gnueabi-gcc -Os -Wall -Wextra -Werror -static -s -march=armv7-a -mfloat-abi=soft firmware/mf79u/src/' + name + '.c -o firmware/mf79u/build/' + name)
subprocess.run(['docker', 'run', '--rm', '-v', str(root) + ':/work', '-w', '/work', 'mf79u-build-tools:local', 'sh', '-eu', '-c', '\n'.join(commands)], check=True)
print('PASS install/SD helpers built.')
