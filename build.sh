#!/usr/bin/env bash
# Render.com build script — install, migrate, collectstatic (free tier has no preDeployCommand).
set -o errexit

pip install --upgrade pip
pip install -r requirements/prod.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear
