#!/usr/bin/env python3
"""MF79U SMS REST client; credentials stay in RAM."""
import argparse
import getpass
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://192.168.0.1')
    parser.add_argument('--password-stdin', action='store_true')
    commands = parser.add_subparsers(dest='command', required=True)
    listing = commands.add_parser('list')
    listing.add_argument('--storage', choices=['modem', 'sim'], default='modem')
    sending = commands.add_parser('send')
    sending.add_argument('number')
    sending.add_argument('--text', help='Omit to read message text from stdin')
    deleting = commands.add_parser('delete')
    deleting.add_argument('ids', nargs='+')
    args = parser.parse_args()
    base = args.url.rstrip('/')
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.path or parsed.query or parsed.fragment:
        parser.error('--url must be an HTTP(S) origin')
    password = sys.stdin.readline().rstrip('\r\n') if args.password_stdin else getpass.getpass('Modem administrator password: ')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    authorization = 'Basic ' + base64.b64encode(('admin:' + password).encode()).decode()
    password = ''

    def request(method, path, data=None):
        headers = {'Authorization': authorization}
        body = None
        if data is not None:
            headers['Content-Type'] = 'application/json'
            body = json.dumps(data, ensure_ascii=False).encode()
        req = urllib.request.Request(base + path, data=body, headers=headers, method=method)
        with opener.open(req, timeout=35) as response:
            return json.load(response)

    try:
        if args.command == 'list':
            result = request('GET', '/api/v1/sms/messages?storage=' + args.storage)
        elif args.command == 'send':
            text = args.text if args.text is not None else sys.stdin.read()
            result = request('POST', '/api/v1/sms/messages', {'number': args.number, 'text': text})
        else:
            result = request('DELETE', '/api/v1/sms/messages', {'ids': args.ids})
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except urllib.error.HTTPError as error:
        try:
            message = json.load(error).get('error', 'Request failed')
        except (ValueError, AttributeError):
            message = 'Request failed'
        print(f'HTTP {error.code}: {message}', file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError):
        print('Modem connection or response failed', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
