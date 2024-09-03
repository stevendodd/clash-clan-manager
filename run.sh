#!/bin/sh

export PYTHONPATH=clashpy
export FLASK_APP=update.py
flask run --port=5001