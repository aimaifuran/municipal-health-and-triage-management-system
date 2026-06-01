#!/usr/bin/env bash
# Local dev server (Git Bash / WSL)
set -e
cd "$(dirname "$0")"
export USE_SQLITE_DEV=1
source .venv/Scripts/activate
python manage.py migrate --noinput
python manage.py runserver
