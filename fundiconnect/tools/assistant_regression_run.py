#!/usr/bin/env python
"""Run a small regression set of prompts against the assistant to observe outputs and logs.

Run from project root with venv active:
python fundiconnect/tools/assistant_regression_run.py
"""
import os
import sys
from pathlib import Path
import json
import logging

# ensure project importable
base = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(base))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fundiconnect.settings')

try:
    import django
    django.setup()
except Exception as e:
    print('Django setup failed:', e)
    sys.exit(2)

# Ensure logs from assistant show up for diagnosis
logging.basicConfig(level=logging.INFO)

from users.assistant import assistant_reply

PROMPTS = [
    "What are the new arrivals?",
    "How many artisans are on the platform with completed jobs? What artisan completed those jobs?",
    "How can I improve my profile?",
    "Can you rewrite my job post?",
    "Show me John's cart",
]

for p in PROMPTS:
    print('\n=== PROMPT ===')
    print(p)
    try:
        r = assistant_reply(p, user=None, context=None, path='/')
        print(json.dumps(r, indent=2, ensure_ascii=False))
    except Exception as e:
        print('Assistant failed for prompt:', p, repr(e))

print('\nRegression run complete. Check logs for GENAI_* entries to see SDK/REST raw responses.')
