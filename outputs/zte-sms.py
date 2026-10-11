#!/usr/bin/env python3
"""Read ZTE goform SMS API; firmware compatibility requires live verification."""
import argparse
import base64
import getpass
import hashlib
import http.cookiejar
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://192.168.0.1')
    parser.add_argument('--login', action='store_true', help='Prompt for web UI password')
    parser.add_argument('--password-file', help='Read web UI password from a protected file')
    parser.add_argument('--password-stdin', action='store_true', help='Read web UI password from stdin')
    parser.add_argument('--auth', choices=['sha256-challenge', 'sha256-base64', 'base64'],
                        default='sha256-challenge', help='Login scheme; default matches verified B03 firmware')
    parser.add_argument('--mem-store', choices=['0', '1'], default='1')
    parser.add_argument('--tags', default='10', help='Firmware SMS folder filter; default 10')
    parser.add_argument('--capacity', action='store_true', help='Include SMS capacity counters')
    args = parser.parse_args()
    root = args.url.rstrip('/')
    parsed = urllib.parse.urlsplit(root)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username:
        parser.error('--url must be an HTTP(S) URL without credentials')
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )

    def request(endpoint, fields, post=False):
        encoded = urllib.parse.urlencode(fields)
        url = root + '/goform/' + endpoint
        body = encoded.encode() if post else None
        if not post:
            url += '?' + encoded
        req = urllib.request.Request(url, data=body, headers={
            'Referer': root + '/index.html',
            'Origin': root,
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
        })
        with opener.open(req, timeout=10) as response:
            return json.load(response)

    if args.login or args.password_file or args.password_stdin:
        if args.password_file:
            with open(args.password_file, encoding='utf-8') as source:
                password = source.read().rstrip('\r\n')
        elif args.password_stdin:
            password = sys.stdin.readline().rstrip('\r\n')
        else:
            password = getpass.getpass('ZTE web UI password: ')
        def sha256(value):
            return hashlib.sha256(value.encode()).hexdigest().upper()
        if args.auth == 'sha256-challenge':
            challenge = request('goform_get_cmd_process', {'isTest': 'false', 'cmd': 'LD'}).get('LD')
            if not challenge:
                raise ValueError('No LD login challenge returned')
            encoded_password = sha256(sha256(password) + challenge)
        elif args.auth == 'sha256-base64':
            encoded_password = sha256(base64.b64encode(password.encode()).decode())
        else:
            encoded_password = base64.b64encode(password.encode()).decode()
        response = request('goform_set_cmd_process', {
            'isTest': 'false', 'goformId': 'LOGIN',
            'password': encoded_password,
        }, post=True)
        del password, encoded_password
        if str(response.get('result')) not in ('0', '4'):
            raise ValueError('Login not confirmed (result=%s); verify firmware login protocol'
                             % response.get('result'))

    messages = []
    for page in range(100):
        response = request('goform_get_cmd_process', {
            'isTest': 'false', 'cmd': 'sms_data_total', 'page': page,
            'data_per_page': 500, 'mem_store': args.mem_store,
            'tags': args.tags, 'order_by': 'order by id desc',
        })
        batch = response.get('messages')
        if not isinstance(batch, list):
            raise ValueError('API did not return messages; login or firmware parameters may differ')
        messages.extend(batch)
        if len(batch) < 500:
            break
    else:
        raise ValueError('Pagination limit exceeded; no partial result emitted')

    capacity = None
    if not messages or args.capacity:
        capacity = request('goform_get_cmd_process', {
            'isTest': 'false', 'cmd': 'sms_capacity_info',
        })
        counters = [int(str(value)) for key, value in capacity.items()
                    if key.startswith('sms_') and re.fullmatch(r'-?\d+', str(value))]
        if any(value < 0 for value in counters):
            raise ValueError('SMS API returned invalid capacity counters; '
                             'the empty list does not confirm an empty SMS inbox')

    for message in messages:
        content = message.get('content', '')
        if (isinstance(content, str) and content and len(content) % 4 == 0
                and re.fullmatch(r'[0-9a-fA-F]+', content)):
            try:
                message['text'] = bytes.fromhex(content).decode('utf-16-be')
            except UnicodeDecodeError:
                message['decode_error'] = 'Content could not be decoded as UTF-16BE'
        else:
            message['text'] = content
    result = {'messages': messages}
    if args.capacity:
        result['capacity'] = capacity
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, urllib.error.URLError) as error:
        print('Error: %s' % error, file=sys.stderr)
        sys.exit(1)
