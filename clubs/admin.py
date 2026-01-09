from django.contrib import admin
from .models import Club, Event, Cellule

class EventAdmin(admin.ModelAdmin):
    # 1. Colonnes visibles dans le tableau de bord
    list_display = ('titre', 'club', 'date', 'budget', 'note_admin')
    
    # 2. Filtres latéraux (Pour afficher seulement les events d'un club ou les mieux notés)
    list_filter = ('club', 'date', 'note_admin')
    
    # 3. Barre de recherche (Chercher par titre)
    search_fields = ('titre', 'description')
    
    # 4. OPTION CLÉ : Permet de modifier le budget et la note SANS ouvrir la fiche détail.
    # L'admin tape la note dans la liste et clique sur "Enregistrer". Gain de temps énorme !
    list_editable = ('budget', 'note_admin')
    
    # 5. Tri par défaut (Les plus récents en premier)
    ordering = ('-date',)

class ClubAdmin(admin.ModelAdmin):
    list_display = ('nom', 'president', 'annee')
    search_fields = ('nom',)

class CelluleAdmin(admin.ModelAdmin):
    list_display = ('nom', 'club', 'event', 'chef')
    list_filter = ('club', 'event')

# Enregistrement des modèles avec leurs configurations
admin.site.register(Event, EventAdmin)
admin.site.register(Club, ClubAdmin)
admin.site.register(Cellule, CelluleAdmin)