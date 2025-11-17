#!/bin/sh

python3 -m venv pyvenv
source pyvenv/bin/activate
python3 -m pip install -r requirements.txt
python3 server.py
export PYTHONPATH=clashpy
export FLASK_APP=update.py
flask run --port=5001 --host=0.0.0.0
deactivate
