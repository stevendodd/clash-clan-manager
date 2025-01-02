#!/bin/sh

export PYTHONPATH=clashpy
export FLASK_APP=update.py
flask run --port=5001 --host=0.0.0.0