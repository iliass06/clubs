from django import forms
from django.core.exceptions import ValidationError
from .models import Annonce, Candidature, Cellule, Event, Club

# ==========================================
# 1. FORMULAIRE ANNONCE (ADMIN)
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
        label="Postes ciblés",
        required=False  # <--- IMPORTANT : On met False pour gérer l'erreur nous-mêmes dans clean()
    )

    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Date de début")
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Date de fin")

    class Meta:
        model = Annonce
        fields = ['titre', 'description', 'club', 'event', 'start_date', 'end_date', 'target_postes', 'cellules']
        widgets = {
            'titre': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'club': forms.Select(attrs={'class': 'form-select'}),
            'event': forms.Select(attrs={'class': 'form-select'}),
            'cellules': forms.SelectMultiple(attrs={'class': 'form-control', 'style': 'height: 100px;'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")
        club = cleaned_data.get("club")
        event = cleaned_data.get("event")
        target_postes = cleaned_data.get("target_postes") # On récupère les postes choisis

        # 1. Validation Dates
        if start and end:
            if end < start:
                self.add_error('end_date', "La date de fin ne peut pas être avant la date de début.")

        # 2. Validation Club / Event (Le fameux message rouge existant)
        if not club and not event:
            raise ValidationError("Veuillez associer cette annonce à au moins un Club ou un Événement.")

        # 3. Validation Postes Ciblés (NOUVEAU MESSAGE ROUGE)
        if not target_postes:
            # On ajoute l'erreur spécifique au champ target_postes
            self.add_error('target_postes', "Veuillez sélectionner au moins un poste ciblé (Président, Chef ou Membre).")

        return cleaned_data


# ==========================================
# 2. FORMULAIRE CANDIDATURE (USER)
# ==========================================
class CandidatureForm(forms.ModelForm):
    profil_souhaite = forms.ChoiceField(
        choices=[], 
        label="Profil souhaité", 
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_profil_souhaite'})
    )
    
    cellule = forms.ModelChoiceField(
        queryset=Cellule.objects.none(),
        required=False,
        label="Cellule",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_cellule'})
    )

    message = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        required=False,
        label="Message (Motivation)"
    )

    class Meta:
        model = Candidature
        fields = ['profil_souhaite', 'cellule', 'message']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None) 
        annonce = kwargs.pop('annonce', None)
        super().__init__(*args, **kwargs)

        if annonce and annonce.target_postes:
            import ast
            try:
                if isinstance(annonce.target_postes, list):
                    postes = annonce.target_postes
                else:
                    postes = ast.literal_eval(annonce.target_postes)
            except:
                postes = []
            self.fields['profil_souhaite'].choices = [(p, p.replace('_', ' ').title()) for p in postes]
        else:
            self.fields['profil_souhaite'].choices = [
                ('membre', 'Membre'), ('chef_cellule', 'Chef cellule'), ('president', 'Président')
            ]

        if annonce:
            queryset = Cellule.objects.none()
            if annonce.club:
                queryset = queryset | annonce.club.cellules.all()
            if annonce.event:
                queryset = queryset | annonce.event.cellules.all()
            self.fields['cellule'].queryset = queryset.distinct()

    def clean(self):
        cleaned_data = super().clean()
        
        profil = cleaned_data.get('profil_souhaite')
        cellule = cleaned_data.get('cellule')

        if profil == 'chef_cellule' and not cellule:
            self.add_error('cellule', "Vous devez obligatoirement choisir une cellule pour postuler comme Chef.")

        return cleaned_data