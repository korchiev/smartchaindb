#!/usr/bin/env python3
import time
import urllib.request

targets = (
    "http://127.0.0.1:9984",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:26657/status",
)
for attempt in range(40):
    ok = True
    for url in targets:
        try:
            urllib.request.urlopen(url, timeout=3)
        except Exception as exc:
            print("wait", attempt, url, type(exc).__name__)
            ok = False
            break
    if ok:
        print("READY")
        raise SystemExit(0)
    time.sleep(3)
print("FAIL")
raise SystemExit(1)
