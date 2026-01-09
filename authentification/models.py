# authentification/models.py
from django.db import models
from django.contrib.auth.models import User

User._meta.get_field('email')._unique = True

class Profil(models.Model):
    ROLE_CHOICES = [
        ('admin','Admin'),
        ('president','President'),
        ('chef_cellule','Chef Cellule'),
        ('membre','Membre'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profil = models.CharField(max_length=20, choices=ROLE_CHOICES, default='membre')
    cne = models.CharField(max_length=20, unique=True, blank=True,null=True, verbose_name="CNE (Code Massar)")
    filiere = models.CharField(max_length=100, blank=True, null=True, verbose_name="Filière")

    def __str__(self):
        return f"{self.user.username} - {self.profil}"









