from django.contrib import admin
from .models import Club, Event, Cellule

# On enregistre les modèles pour qu'ils soient visibles dans l'interface admin
admin.site.register(Club)
admin.site.register(Event)
admin.site.register(Cellule)