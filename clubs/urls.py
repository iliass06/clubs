from django.urls import path
from . import views

urlpatterns = [
    # Liste clubs et events (page principale de gestion)
    path('gestion/', views.gestion_club_event, name='gestion_club_event'),

    # CRUD Club
    path('club/create/', views.club_create, name='club_create'),
    path('club/<int:pk>/update/', views.club_update, name='club_update'),
    path('club/<int:pk>/delete/', views.club_delete, name='club_delete'),

    # CRUD Event
    path('event/create/', views.event_create, name='event_create'),
    path('event/<int:pk>/update/', views.event_update, name='event_update'),
    path('event/<int:pk>/delete/', views.event_delete, name='event_delete'),
]
