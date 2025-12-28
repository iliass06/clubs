from django.db import models
from clubs.models import Club, Cellule
from django.contrib.auth.models import User
from django.utils import timezone

class Notification(models.Model):
    VISIBLE = [('chefs','Chefs'), ('membres','Membres'), ('all','Tous'), ('cellule','Cellule')]
    titre = models.CharField(max_length=200)
    message = models.TextField()
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='notifications_sent')
    club = models.ForeignKey(Club, null=True, blank=True, on_delete=models.CASCADE)
    cellule = models.ForeignKey(Cellule, null=True, blank=True, on_delete=models.CASCADE)
    visible_par = models.CharField(max_length=20, choices=VISIBLE, default='all')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.titre} ({self.club})"
