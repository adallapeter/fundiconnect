import json
import time
import threading
from websocket import WebSocketApp

WS_URL = 'ws://127.0.0.1:8000/ws/assistant/'

received = []

def on_message(ws, message):
    try:
        payload = json.loads(message)
    except Exception:
        print('RAW:', message)
        return
    print('RECV:', json.dumps(payload, indent=2))
    received.append(payload)


def on_error(ws, error):
    print('ERROR:', error)


def on_close(ws, close_status_code, close_msg):
    print('CLOSED', close_status_code, close_msg)


def on_open(ws):
    print('OPEN')
    # Inform the server we're ready (no auth for guest)
    time.sleep(0.1)
    msg = {
        'type': 'generate',
        'prompt': 'Hello, run a quick connectivity test and tell me the platform counts.',
        'path': '/home/',
        'context': []
    }
    ws.send(json.dumps(msg))
    # Also send a typing signal to test typing events
    time.sleep(0.2)
    ws.send(json.dumps({'type': 'typing', 'actor': 'user', 'is_typing': True}))
    time.sleep(0.6)
    ws.send(json.dumps({'type': 'typing', 'actor': 'user', 'is_typing': False}))


if __name__ == '__main__':
    ws = WebSocketApp(WS_URL, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close)

    # run in thread so we can time out
    wst = threading.Thread(target=ws.run_forever, kwargs={'ping_interval': 10, 'ping_timeout': 5})
    wst.daemon = True
    wst.start()

    # Wait up to 20 seconds for messages
    timeout = 20
    start = time.time()
    try:
        while time.time() - start < timeout:
            time.sleep(0.5)
            # if we got an assistant_response, break
            if any((p.get('type') == 'assistant_response' or (p.get('type') == 'assistant_state')) for p in received):
                break
    except KeyboardInterrupt:
        pass

    print('Done; received', len(received), 'messages')
    ws.close()
