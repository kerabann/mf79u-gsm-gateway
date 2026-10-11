"""Publication, syntax, local documentation and complete migration audit."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
REPORTS.mkdir(exist_ok=True)


def candidate_files():
    result = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT)
    return sorted({ROOT / name.decode() for name in result.split(b'\0') if name and (ROOT / name.decode()).is_file()})


def lint():
    files = candidate_files()
    for path in files:
        if path.suffix == '.py':
            ast.parse(path.read_text(), filename=str(path.relative_to(ROOT)))
        elif path.suffix == '.sh' or path == ROOT / 'outputs/adb':
            subprocess.run(['sh', '-n', str(path)], check=True)
        elif path.suffix == '.js':
            subprocess.run(['node', '--check', str(path)], check=True)
    print('PASS Python/shell/JavaScript syntax.')


def migration(strict=False):
    manifest = json.loads((ROOT / 'docs/migration-manifest.json').read_text())
    bad = []
    changed = []
    kinds = {}
    for row in manifest['files']:
        dest = ROOT / row['destination']
        if not dest.is_file():
            bad.append(row['destination'] + ': missing')
        elif hashlib.sha256(dest.read_bytes()).hexdigest() != row['destination_sha256']:
            changed.append(row['destination'])
            if strict:
                bad.append(row['destination'] + ': changed from migration receipt')
        kinds[dest.suffix] = kinds.get(dest.suffix, 0) + 1
    report = {'passed': not bad, 'importedFiles': len(manifest['files']), 'bySuffix': kinds, 'failures': bad, 'changedSinceMigration': changed, 'strictFingerprints': strict,
              'exclusions': manifest['excluded'], 'deviceTest': False}
    (REPORTS / 'migration.json').write_text(json.dumps(report, indent=2) + '\n')
    if bad:
        raise SystemExit('Migration audit failed: ' + '; '.join(bad[:10]))
    print('PASS migration:', len(manifest['files']), 'imported files;', 'every destination fingerprint.' if strict else 'coverage retained; intentional later edits allowed.')


def publication():
    files = candidate_files()
    forbidden = {'settings.json', 'gateway.ini', 'phone.json', 'connection.json', 'ssh.password', '.env'}
    issues = []
    for path in files:
        rel = path.relative_to(ROOT)
        if path.name in forbidden or path.suffix in {'.pcap', '.pcapng', '.wav', '.bin', '.ko', '.so', '.pem', '.key', '.gz', '.a', '.o'}:
            issues.append(str(rel) + ': private/generated artifact')
        if any(part in {'private', '.venv', '__pycache__'} for part in rel.parts) or 'build' in rel.parts:
            issues.append(str(rel) + ': generated/private directory')
        if path.is_symlink():
            issues.append(str(rel) + ': symlink must be reviewed')
        try:
            text = path.read_text()
        except UnicodeError:
            continue
        patterns = [r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',
                    r'\b(?:ghp_|github_pat_|glpat-)[A-Za-z0-9_\-]{15,}',
                    r'\bAKIA[A-Z0-9]{16}\b', r'/Users/' + r'keraban/',
                    r'(?i)(?:live_api_key|actual_password)\s*=\s*[\"\'][^\"\']{12,}']
        if any(re.search(pattern, text) for pattern in patterns):
            issues.append(str(rel) + ': sensitive/personal pattern (value omitted)')
    # Scan only publication candidates, not ignored local credentials/dumps.
    scanner = ['gitleaks'] if shutil.which('gitleaks') and os.environ.get('GITLEAKS') != 'go' else ['go', 'run', 'github.com/zricethezav/gitleaks/v8@v8.30.1']
    with tempfile.TemporaryDirectory(prefix='mf79u-publication-scan-') as directory:
        for path in files:
            dest = Path(directory) / path.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        command = scanner + ['dir', directory, '--config', str(ROOT / '.gitleaks.toml'), '--no-banner', '--redact', '--report-format', 'json', '--report-path', str(REPORTS / 'gitleaks.json')]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode:
            issues.append('gitleaks: findings or scanner failure; see redacted local report')
    report = {'passed': not issues, 'candidateFiles': len(files), 'issues': issues, 'gitleaksExecuted': True}
    (REPORTS / 'publication.json').write_text(json.dumps(report, indent=2) + '\n')
    if issues:
        raise SystemExit('Publication audit failed: ' + '; '.join(issues[:10]))
    print('PASS publication allowlist and secret scan:', len(files), 'files.')


def documentation():
    issues = []
    links = 0
    docs = [p for p in candidate_files() if p.suffix == '.md']
    for path in docs:
        text = path.read_text()
        for match in re.finditer(r'!?\[[^\]]*\]\(([^)]+)\)', text):
            target = match[1].split(' "', 1)[0].strip('<>')
            u = urllib.parse.urlsplit(target)
            if u.scheme or target.startswith('#'):
                continue
            target = urllib.parse.unquote(u.path)
            links += 1
            if target and not (path.parent / target).exists():
                issues.append(str(path.relative_to(ROOT)) + ': ' + target)
    report = {'passed': not issues, 'markdownFiles': len(docs), 'localLinks': links, 'brokenLinks': issues}
    (REPORTS / 'documentation.json').write_text(json.dumps(report, indent=2) + '\n')
    if issues:
        raise SystemExit('Documentation audit failed: ' + '; '.join(issues[:12]))
    print('PASS', len(docs), 'Markdown documents and', links, 'local links.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lint', action='store_true')
    parser.add_argument('--migration', action='store_true')
    parser.add_argument('--publication', action='store_true')
    parser.add_argument('--strict', action='store_true')
    args = parser.parse_args()
    if args.lint:
        lint()
    elif args.migration:
        migration(args.strict)
    elif args.publication:
        publication()
    else:
        documentation()


if __name__ == '__main__':
    main()
