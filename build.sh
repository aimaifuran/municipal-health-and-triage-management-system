#!/usr/bin/env bash
# Render.com build script — installs dependencies and collects static files.
set -o errexit

pip install --upgrade pip
pip install -r requirements/prod.txt
python manage.py collectstatic --noinput --clear
