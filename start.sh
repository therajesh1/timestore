#!/usr/bin/env bash
# exit on error
set -o errexit

# Run migrations
python manage.py migrate

# Seed database
python manage.py seed_brands
python manage.py seed_products

# Start server
gunicorn config.wsgi
