# authentification/models.py
from django.db import models
from django.contrib.auth.models import User

class Profil(models.Model):
    ROLE_CHOICES = [
        ('admin','Admin'),
        ('president','President'),
        ('chef_cellule','Chef Cellule'),
        ('membre','Membre'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profil = models.CharField(max_length=20, choices=ROLE_CHOICES, default='membre')

    def __str__(self):
        return f"{self.user.username} - {self.profil}"
