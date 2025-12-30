from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Profil

# ==========================================
# 1. FORMULAIRE D'INSCRIPTION (USER + PROFIL)
# ==========================================
class SignUpForm(UserCreationForm):
    # On rend ces champs obligatoires et on les affiche proprement
    first_name = forms.CharField(max_length=30, required=True, label="Prénom")
    last_name = forms.CharField(max_length=30, required=True, label="Nom")
    email = forms.EmailField(max_length=254, required=True, label="Adresse Email")

    # Nouveaux champs pour le modèle Profil
    cne = forms.CharField(max_length=20, required=True, label="CNE (Code Massar)")
    
    # Tes filières exactes avec l'abréviation ajoutée devant pour l'affichage
    FILIERE_CHOICES = [
        ('', 'Choisir une filière...'),
        
        ('API1', 'API1 - Cycle Préparatoire 1'),
        ('API2', 'API2 - Cycle Préparatoire 2'),
        
        ('IID1', 'IID1 - Informatique et Ingénierie Données 1'),
        ('IID2', 'IID2 - Informatique et Ingénierie Données 2'),
        ('IID3', 'IID3 - Informatique et Ingénierie Données 3'),
        
        ('IRIC1', 'IRIC1 - Réseaux et Télécoms 1'),
        ('IRIC2', 'IRIC2 - Réseaux et Télécoms 2'),
        ('IRIC3', 'IRIC3 - Réseaux et Télécoms 3'),
        
        ('GI1', 'GI1 - Génie Informatique 1'),
        ('GI2', 'GI2 - Génie Informatique 2'),
        ('GI3', 'GI3 - Génie Informatique 3'),
        
        ('GE1', 'GE1 - Génie Électrique 1'),
        ('GE2', 'GE2 - Génie Électrique 2'),
        ('GE3', 'GE3 - Génie Électrique 3'),
        
        ('GPEE1', 'GPEE1 - Génie des Procédés et Environnement 1'),
        ('GPEE2', 'GPEE2 - Génie des Procédés et Environnement 2'),
        ('GPEE3', 'GPEE3 - Génie des Procédés et Environnement 3'),
        
        ('MGSI1', 'MGSI1 - Management et Gestion des Systèmes d\'Information 1'),
        ('MGSI2', 'MGSI2 - Management et Gestion des Systèmes d\'Information 2'),
        ('MGSI3', 'MGSI3 - Management et Gestion des Systèmes d\'Information 3'),
        
        ('MST', 'MST - Master'),
    ]
    filiere = forms.ChoiceField(choices=FILIERE_CHOICES, required=True, label="Filière")

    class Meta(UserCreationForm.Meta):
        model = User
        # On définit l'ordre d'affichage des champs dans le formulaire
        fields = ('username', 'first_name', 'last_name', 'email', 'cne', 'filiere')

    def save(self, commit=True):
        # 1. Sauvegarde de l'utilisateur standard
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            # 2. Création automatique du Profil avec CNE et Filière
            Profil.objects.update_or_create(
                user=user,
                defaults={
                    'cne': self.cleaned_data['cne'],
                    'filiere': self.cleaned_data['filiere'],
                    'profil': 'membre'  # Par défaut, c'est un membre
                }
            )
        return user

# ==========================================
# 2. FORMULAIRE DE MODIFICATION ADMIN
# ==========================================
class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }