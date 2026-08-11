from pathlib import Path
import json
import urllib.request
import urllib.error

text = Path('.env').read_text(encoding='utf-8')
token = next(line.split('=', 1)[1].strip() for line in text.splitlines() if line.startswith('MISSKEY_ACCESS_TOKEN='))
req = urllib.request.Request(
    'https://mi.kyanos.one/api/notes/global-timeline',
    data=json.dumps({'i': token, 'limit': 3}).encode('utf-8'),
    headers={'User-Agent': 'MiChannelAutoRenoter/1.0', 'Content-Type': 'application/json'},
    method='POST',
)
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        print('status', r.status)
        print(r.read().decode('utf-8', 'ignore')[:800])
except urllib.error.HTTPError as e:
    print('status', e.code)
    print(e.read().decode('utf-8', 'ignore')[:800])
