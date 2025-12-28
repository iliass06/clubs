from django import forms
from .models import Cellule, Club, Event

class ClubForm(forms.ModelForm):
    class Meta:
        model = Club
        fields = ['nom', 'description', 'annee', 'coordinateur','image']

        

class EventForm(forms.ModelForm):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))  # date picker HTML5

    class Meta:
        model = Event
        fields = ['titre', 'description', 'date', 'club', 'image']


class CelluleForm(forms.ModelForm):
    class Meta:
        model = Cellule
        fields = ['nom', 'description']





# Formsets
ClubCelluleFormSet = forms.inlineformset_factory(
    Club, Cellule, form=CelluleForm, extra=1, can_delete=True
)

EventCelluleFormSet = forms.inlineformset_factory(
    Event, Cellule, form=CelluleForm, extra=1, can_delete=True
)