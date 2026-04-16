#!/usr/bin/env python
"""Simple diagnostic to prove the assistant pipeline invokes the model.

Run from the project root with your virtualenv activated:

python fundiconnect/tools/assistant_check.py "How many artisans are on the platform?"

The script prints env/model info and the assistant JSON response.
"""
import os
import sys
import json
from pathlib import Path

# Ensure the project root is on sys.path (so Python can import the inner "fundiconnect" package).
# Walk upward and add the first ancestor that contains a `fundiconnect` package directory with `__init__.py`.
base = Path(__file__).resolve()
added = False
for i in range(1, 6):
    candidate = base.parents[i]
    pkg_init = candidate / 'fundiconnect' / '__init__.py'
    if pkg_init.exists():
        sys.path.insert(0, str(candidate))
        added = True
        break

if not added:
    # Fallbacks: try a couple of likely parents
    try:
        sys.path.insert(0, str(base.parents[2]))
    except Exception:
        pass
# Ensure Django settings are found like manage.py
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fundiconnect.settings')

try:
    import django
    django.setup()
except Exception as e:
    print("Failed to setup Django:", e)
    sys.exit(2)

try:
    from users.assistant import assistant_reply, _gemini_models
    from django.conf import settings
except Exception as e:
    print("Failed to import assistant module:", e)
    sys.exit(3)

prompt = "How many artisans are on the platform?"
if len(sys.argv) > 1:
    prompt = sys.argv[1]

print("=== Diagnostic: FundiConnect Assistant Check ===")
print("GEMINI_API_KEY present:", bool(os.environ.get('GEMINI_API_KEY') or getattr(settings, 'GEMINI_API_KEY', None)))
print("Gemini model candidates:", _gemini_models())
print("System instruction (trimmed):", (os.environ.get('FUNDICONNECT_ASSISTANT_SYSTEM_INSTRUCTION') or getattr(settings, 'FUNDICONNECT_ASSISTANT_SYSTEM_INSTRUCTION', ''))[:200])
print()

print("Running assistant_reply() with prompt:", prompt)
try:
    resp = assistant_reply(prompt, user=None, context=None, path="/")
    print(json.dumps(resp, indent=2, ensure_ascii=False))
except Exception as e:
    print("Assistant call failed:", repr(e))
    sys.exit(4)

print("\nIf the output contains 'text' and suggestions/highlights, the assistant pipeline returned a structured response. If you expect a live model call but see only fallback text, ensure GEMINI_API_KEY is set and reachable from this environment.")
