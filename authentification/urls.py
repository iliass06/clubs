from django.urls import path
from . import views
from recrutement import views as rec_views

urlpatterns = [
    path('', views.home, name='home'),  # homepage
    path('signin/', views.signin, name='signin'),
    path('signout/', views.signout, name='signout'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # --- CORRECTION ICI ---
    # On remplace rec_views.create_annonce par rec_views.gerer_annonce
    path('admin-dashboard/annonce/create/', rec_views.gerer_annonce, name='create_annonce'),
    
    path('president/dashboard/', views.president_dashboard, name='president_dashboard'),
    path('chef/dashboard/', views.chef_dashboard, name='chef_dashboard'),
    path('membre/dashboard/', views.membre_dashboard, name='membre_dashboard'),
    
    path('gestion-utilisateurs/', views.gestion_utilisateurs, name='gestion_utilisateurs'),
    path('utilisateur/<int:user_id>/desactiver/', views.desactiver_utilisateur, name='desactiver_utilisateur'),
    path('utilisateur/modifier/<int:user_id>/', views.modifier_utilisateur, name='modifier_utilisateur'),
    path('supprimer-utilisateur/<int:user_id>/', views.supprimer_utilisateur, name='supprimer_utilisateur'),
]
