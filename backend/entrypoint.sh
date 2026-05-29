#!/bin/sh
set -e

flask --app wsgi:app db upgrade
flask --app wsgi:app seed-data

exec gunicorn -b 0.0.0.0:5001 wsgi:app
