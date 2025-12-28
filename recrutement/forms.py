from django import forms
from django.core.exceptions import ValidationError
from .models import Annonce, Candidature, Cellule, Event, Club

# ==========================================
# 1. FORMULAIRE ANNONCE
# ==========================================
class AnnonceForm(forms.ModelForm):
    TARGET_CHOICES = [
        ('president', 'Président'),
        ('chef_cellule', 'Chef de cellule'),
        ('membre', 'Membre')
    ]

    target_postes = forms.MultipleChoiceField(
        choices=TARGET_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Postes ciblés"
    )

    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Date de début")
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Date de fin")

    class Meta:
        model = Annonce
        fields = ['titre', 'description', 'club', 'event', 'start_date', 'end_date', 'target_postes', 'cellules']

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")

        if start and end:
            if end < start:
                self.add_error('end_date', "La date de fin ne peut pas être avant la date de début.")
        
        return cleaned_data


# ==========================================
# 2. FORMULAIRE CANDIDATURE (Avec Password)
# ==========================================
class CandidatureForm(forms.ModelForm):
    # Les champs sont définis ici, mais on va peut-être les supprimer dynamiquement dans __init__
    prenom = forms.CharField(max_length=150, required=False, label="Prénom", widget=forms.TextInput(attrs={'class': 'form-control'}))
    nom = forms.CharField(max_length=150, required=False, label="Nom", widget=forms.TextInput(attrs={'class': 'form-control'}))
    username = forms.CharField(max_length=150, required=False, label="Nom d'utilisateur", widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=False, label="Email", widget=forms.EmailInput(attrs={'class': 'form-control'}))

    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirmez le mot de passe', 'class': 'form-control'}),
        label="Confirmation du mot de passe",
        required=False
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Mot de passe souhaité', 'class': 'form-control'}),
        label="Mot de passe",
        required=False
    )

    profil_souhaite = forms.ChoiceField(choices=[], label="Profil souhaité", widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_profil_souhaite'}))
    
    cellule = forms.ModelChoiceField(
        queryset=Cellule.objects.none(),
        required=False,
        label="Cellule",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_cellule'})
    )

    message = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False,
        label="Message"
    )

    class Meta:
        model = Candidature
        fields = ['prenom', 'nom', 'username', 'email', 'password', 'profil_souhaite', 'cellule', 'message']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None) # On récupère l'utilisateur passé par la vue
        annonce = kwargs.pop('annonce', None)
        super().__init__(*args, **kwargs)

        # SI L'UTILISATEUR EST CONNECTÉ : On supprime les champs d'identité du formulaire
        if self.user and self.user.is_authenticated:
            del self.fields['prenom']
            del self.fields['nom']
            del self.fields['username']
            del self.fields['email']
            del self.fields['password']
            del self.fields['confirm_password']
        else:
            # Sinon, on s'assure qu'ils sont requis
            self.fields['prenom'].required = True
            self.fields['nom'].required = True
            self.fields['username'].required = True
            self.fields['email'].required = True
            self.fields['password'].required = True
            self.fields['confirm_password'].required = True

        # Gestion dynamique des choix (profils et cellules) - CODE EXISTANT
        if annonce and annonce.target_postes:
            import ast
            try:
                # Si c'est une liste
                if isinstance(annonce.target_postes, list):
                    postes = annonce.target_postes
                else:
                    # Si c'est une string "['a', 'b']"
                    postes = ast.literal_eval(annonce.target_postes)
            except:
                postes = []
            
            self.fields['profil_souhaite'].choices = [(p, p.replace('_', ' ').title()) for p in postes]
        else:
            self.fields['profil_souhaite'].choices = [
                ('membre', 'Membre'), ('chef_cellule', 'Chef cellule'), ('president', 'Président')
            ]

        if annonce:
            if annonce.club:
                self.fields['cellule'].queryset = annonce.club.cellules.all()
            elif annonce.event:
                self.fields['cellule'].queryset = annonce.event.cellules.all()

    def clean(self):
        cleaned_data = super().clean()
        
        # Validation mot de passe UNIQUEMENT si l'utilisateur n'est pas connecté
        if not (self.user and self.user.is_authenticated):
            pwd = cleaned_data.get("password")
            confirm = cleaned_data.get("confirm_password")
            if pwd and confirm and pwd != confirm:
                self.add_error('confirm_password', "Les mots de passe ne correspondent pas.")
        
        return cleaned_data