#!/usr/bin/env bash
# Render.com build script — install, migrate, seed demo data, collectstatic (free tier has no Shell/preDeploy).
set -o errexit

pip install --upgrade pip
pip install -r requirements/prod.txt
python manage.py migrate --noinput
# Free Render tier has no Shell; --reset clears PAT-SAMPLE* patients so redeploys do not duplicate triage rows.
python manage.py seed_demo --reset
python manage.py collectstatic --noinput --clear
