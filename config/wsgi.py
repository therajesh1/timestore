"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import django
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Initialize Django and run database setup automatically
try:
    django.setup()
    from django.core.management import call_command
    print("Running database migrations...")
    call_command('migrate', interactive=False)
    print("Seeding database (brands)...")
    call_command('seed_brands')
    print("Seeding database (products)...")
    call_command('seed_products')
    print("Database setup completed successfully.")
except Exception as e:
    print(f"Error running database setup during WSGI initialization: {e}")

application = get_wsgi_application()
