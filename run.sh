#!/bin/sh

VENV_DIR=$(mktemp -d)
trap 'rm -rf "$VENV_DIR"' EXIT

python3 -m venv "$VENV_DIR"
. "$VENV_DIR/bin/activate"
python3 -m pip install -q -r requirements.txt
export PYTHONPATH=clashpy
export FLASK_APP=update.py
flask run --port=5001 --host=0.0.0.0
