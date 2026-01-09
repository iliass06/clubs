# clubs/models.py
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator  # <--- Import nécessaire pour borner la note

class Club(models.Model):
    nom = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    annee = models.PositiveIntegerField(null=True, blank=True)
    president = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='preside_clubs')
    coordinateur = models.CharField(max_length=150, blank=True, null=True)
    membres = models.ManyToManyField(User, blank=True, related_name='membres_club')
    image = models.ImageField(upload_to='clubs/', null=True, blank=True)

    def __str__(self):
        return self.nom

class Event(models.Model):
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    club = models.ForeignKey(Club, null=True, blank=True, on_delete=models.CASCADE, related_name='events')
    president = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='events_president')
    chefs = models.ManyToManyField(User, blank=True, related_name='events_chefs')
    image = models.ImageField(upload_to='events/', null=True, blank=True)

    # --- NOUVEAUX CHAMPS STATISTIQUES ---
    budget = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, 
        verbose_name="Budget Alloué (DH)"
    )
    
    note_admin = models.PositiveSmallIntegerField(
        null=True, 
        blank=True, 
        validators=[MinValueValidator(0), MaxValueValidator(20)], # Note validée entre 0 et 20
        verbose_name="Note Admin (/20)"
    )

    def __str__(self):
        note_str = f"{self.note_admin}/20" if self.note_admin is not None else "Non noté"
        return f"{self.titre} ({note_str})"
    
class Cellule(models.Model):
    nom = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    club = models.ForeignKey(Club, null=True, blank=True, on_delete=models.CASCADE, related_name='cellules')
    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.CASCADE, related_name='cellules')
    chef = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='chef_cellules')
    membres = models.ManyToManyField(User, blank=True, related_name='membres_cellule')

    class Meta:
        unique_together = ('nom', 'club', 'event')  # unique par club ou par event

    def __str__(self):
        parent = self.club.nom if self.club else (self.event.titre if self.event else "Sans parent")
        return f"{self.nom} ({parent})"