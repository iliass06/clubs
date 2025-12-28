# recrutement/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # --- MODIFICATION ICI ---
    # 1. Pour CRÉER : On garde le même nom 'create_annonce' (pour ne pas casser tes liens) 
    # mais on pointe vers la nouvelle vue 'gerer_annonce'
    path('create-annonce/', views.gerer_annonce, name='create_annonce'),

    # 2. Pour MODIFIER : Nouvelle URL qui prend un ID et pointe aussi vers 'gerer_annonce'
    path('annonce/modifier/<int:id>/', views.gerer_annonce, name='modifier_annonce'),
    # ------------------------

    # Le reste ne change pas
    path('ajax/load-cells-events/', views.load_cells_events, name='ajax_load_cells_events'),
    path('postuler/<int:annonce_id>/', views.postuler, name='postuler'),
    path('admin-candidatures/<int:annonce_id>/', views.admin_candidatures, name='admin_candidatures'),
    path('traiter-candidature/<int:cand_id>/<str:action>/', views.traiter_candidature, name='traiter_candidature'),
    path('delete_annonce/<int:annonce_id>/', views.delete_annonce, name='delete_annonce'),
]