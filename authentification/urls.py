# authentification/urls.py
from django.urls import path
from . import views
from recrutement import views as rec_views

urlpatterns = [
    # Pages publiques
    path('', views.home, name='home'),
    path('signin/', views.signin, name='signin'),
    path('signout/', views.signout, name='signout'),
    path('signup/', views.signup, name='signup'),

    # Espace Admin
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('gestion-utilisateurs/', views.gestion_utilisateurs, name='gestion_utilisateurs'),
    
    # Actions Admin sur les utilisateurs
    path('utilisateur/modifier/<int:user_id>/', views.modifier_utilisateur, name='modifier_utilisateur'),
    path('supprimer-utilisateur/<int:user_id>/', views.supprimer_utilisateur, name='supprimer_utilisateur'),
    path('desactiver_utilisateur/<int:user_id>/<str:action>/', views.desactiver_utilisateur, name='desactiver_utilisateur'),

    # Gestion des annonces (Admin)
    path('admin-dashboard/annonce/create/', rec_views.gerer_annonce, name='create_annonce'),
    path('gestion/noter-event/<int:event_id>/', views.noter_event, name='noter_event'),
    
    # Espace Membre & Actions
    path('membre/dashboard/', views.membre_dashboard, name='membre_dashboard'),
    path('quitter/<str:type_objet>/<int:id_objet>/<str:role>/', views.quitter_poste, name='quitter_poste'),
]