"""Run make ci from the Git index and checksum-verified upstream cache."""
from pathlib import Path
import json
import os
import subprocess
import tempfile


def export_index(root, destination):
    """Export staged contents; local/untracked files must not mask omissions."""
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'checkout-index', '--all', '--prefix=' + str(destination.resolve()) + os.sep],
                   cwd=root, check=True)


def main():
    root = Path(__file__).resolve().parents[1]
    dest = Path(tempfile.mkdtemp(prefix='mf79u-clean-checkout-'))
    export_index(root, dest)
    subprocess.run(['git', 'init', '--quiet', str(dest)], check=True)
    env = dict(os.environ, SOURCE_CACHE=str(root))
    env.pop('ADB', None)
    env.pop('ANDROID_SERIAL', None)
    reports = root / 'reports'
    reports.mkdir(exist_ok=True)
    print('Clean Git-index checkout:', dest, flush=True)
    print('Untracked and unstaged contents excluded; stage intended changes before running.', flush=True)
    print('Reusing checksum-verified upstream archives only; no vendor dump, source tree or build artifact.', flush=True)
    with (reports / 'clean-checkout.log').open('w') as log:
        result = subprocess.run(['make', 'ci'], cwd=dest, env=env, stdout=log, stderr=subprocess.STDOUT)
    report = {'passed': result.returncode == 0, 'checkout': str(dest), 'source': 'git-index',
              'untrackedFilesIncluded': False, 'unstagedContentsIncluded': False,
              'vendorInputs': False, 'buildArtifactsReused': False,
              'upstreamArchiveCacheReused': True, 'githubHostedRun': False}
    (reports / 'clean-checkout.json').write_text(json.dumps(report, indent=2) + '\n')
    if result.returncode:
        raise SystemExit('Clean make ci failed; see reports/clean-checkout.log')
    print('PASS clean Git-index checkout: complete make ci, no proprietary/private input.')


if __name__ == '__main__':
    main()
