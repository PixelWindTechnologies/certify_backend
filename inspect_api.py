import json
import ssl
import urllib.request

ctx = ssl._create_unverified_context()
req = urllib.request.Request(
    'http://localhost:8000/api/v1/auth/login',
    method='POST',
    data=json.dumps({'email':'admin@pixelwind.in','password':'ChangeMe123!'}).encode(),
    headers={'Content-Type':'application/json'},
)
with urllib.request.urlopen(req, context=ctx) as r:
    login = json.loads(r.read().decode())

headers = {'Authorization': f"Bearer {login['access_token']}"}
for path in ['/api/v1/enrollments', '/api/v1/students']:
    req = urllib.request.Request('http://localhost:8000' + path, headers=headers)
    with urllib.request.urlopen(req, context=ctx) as r:
        data = json.loads(r.read().decode())
    print('PATH', path)
    if isinstance(data, list):
        print(json.dumps(data[:2], indent=2)[:4000])
    else:
        print(json.dumps(data, indent=2)[:4000])
