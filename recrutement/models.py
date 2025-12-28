from django.db import models
from clubs.models import Club, Cellule, Event
from django.contrib.auth.models import User
from django.utils import timezone

class Annonce(models.Model):
    PUBLISHER_CHOICES = [('admin','Admin'), ('president','President')]
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    club = models.ForeignKey(Club, null=True, blank=True, on_delete=models.SET_NULL)
    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.SET_NULL)
    publisher = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='annonces_publishers')
    publisher_type = models.CharField(max_length=20, choices=PUBLISHER_CHOICES, default='admin')
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    target_postes = models.JSONField(default=list)  # ex: ['president','chef_cellule'] ou ['membre']
    cellules = models.ManyToManyField(Cellule, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_active(self):
        now = timezone.now()
        return self.start_date <= now <= self.end_date

    def __str__(self):
        return self.titre


class Candidature(models.Model):
    STATUS = [('en_attente','En attente'), ('acceptee','Acceptée'), ('refusee','Refusée')]
    annonce = models.ForeignKey(Annonce, on_delete=models.CASCADE, related_name='candidatures')
    # AJOUT !!!
    prenom = models.CharField(max_length=150)
    nom = models.CharField(max_length=150)
    username = models.CharField(max_length=150)
    email = models.EmailField()
    password = models.CharField(max_length=128)
    profil_souhaite = models.CharField(max_length=20)
    cellule = models.ForeignKey(Cellule, null=True, blank=True, on_delete=models.SET_NULL)
    club = models.ForeignKey(Club, null=True, blank=True, on_delete=models.SET_NULL)
    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.SET_NULL)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='en_attente')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='processed_candidatures')

    def __str__(self):
        return f"{self.username} → {self.profil_souhaite} ({self.annonce.titre})"



class Membership(models.Model):
    ROLE = [('president','President'), ('chef_cellule','Chef Cellule'), ('membre','Membre')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='memberships')
    cellule = models.ForeignKey(Cellule, null=True, blank=True, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLE, default='membre')
    date_joined = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user','club','cellule','role')

    def __str__(self):
        return f"{self.user.username} - {self.role} @ {self.club.nom} / {self.cellule}"
