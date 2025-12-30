"""
WSGI config for skispot project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skispot.settings')

application = get_wsgi_application()

