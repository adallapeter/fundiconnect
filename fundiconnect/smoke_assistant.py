import requests, time, json, sys

BASE = 'http://127.0.0.1:8000'
session = requests.Session()

# Wait for server to become available
for i in range(20):
    try:
        r = session.get(BASE + '/accounts/login/', timeout=3)
        # prefer login page to ensure a CSRF cookie is set
        if r.status_code == 200:
            break
    except Exception as e:
        print('waiting for server...', i)
        time.sleep(0.5)
else:
    print('server did not start in time')
    sys.exit(2)

# Try to read CSRF cookie from session
csrf = session.cookies.get('csrftoken') or session.cookies.get('csrf') or ''
print('csrf token:', csrf)

payload = {
    'prompt': 'Hello FundiConnect assistant, how many artisans are currently available?',
    'path': '/home/',
    'context': []
}
headers = {'Content-Type': 'application/json'}
if csrf:
    headers['X-CSRFToken'] = csrf

try:
    r = session.post(BASE + '/accounts/assistant/respond/', json=payload, headers=headers, timeout=30)
    print('POST status', r.status_code)
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)
except Exception as e:
    print('request failed', str(e))
    sys.exit(3)
