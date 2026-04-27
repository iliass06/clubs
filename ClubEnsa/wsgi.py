"""
WSGI config for ClubEnsa project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

#import os

#from django.core.wsgi import get_wsgi_application

#os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ClubEnsa.settings")

#application = get_wsgi_application()


import os
import sys
from django.core.wsgi import get_wsgi_application

# Ajoute le dossier racine au PATH pour que Python trouve les apps (authentification, clubs, etc.)
path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if path not in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ClubEnsa.settings')

application = get_wsgi_application()

# Pour Vercel
app = application
