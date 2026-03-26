#!/usr/bin/env bash
set -o errexit

export DEBUG="${DEBUG:-true}"
export SECRET_KEY="${SECRET_KEY:-build-secret-key}"

python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
