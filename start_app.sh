#!/usr/bin/env sh
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python desktop_app.py
else
  exec python desktop_app.py
fi
