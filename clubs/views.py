from django.shortcuts import render, get_object_or_404, redirect
from .models import Cellule, Club, Event
from .forms import CelluleForm, ClubCelluleFormSet, ClubForm, EventCelluleFormSet, EventForm
from django.forms import inlineformset_factory
# Page principale Gestion Club/Event
from .forms import ClubForm, EventForm, ClubCelluleFormSet, EventCelluleFormSet

def gestion_club_event(request):
    clubs = Club.objects.all()
    events = Event.objects.all()

    # Formulaires pour la création
    club_form = ClubForm()
    club_cellule_formset = ClubCelluleFormSet(queryset=Cellule.objects.none(), prefix='club')
    
    event_form = EventForm()
    event_cellule_formset = EventCelluleFormSet(queryset=Cellule.objects.none(), prefix='event')

    # Formulaires pour l'édition (par club/event)
    club_forms = {club.id: ClubForm(instance=club) for club in clubs}
    event_forms = {event.id: EventForm(instance=event) for event in events}

    return render(request, 'clubs/gestion.html', {
        'clubs': clubs,
        'events': events,
        'club_form': club_form,
        'club_cellule_formset': club_cellule_formset,
        'event_form': event_form,
        'event_cellule_formset': event_cellule_formset,
        'club_forms': club_forms,
        'event_forms': event_forms,
    })



# ---------- CRUD Club ----------
from django.contrib import messages  # Assure-toi d'avoir cet import en haut

def club_create(request):
    if request.method == 'POST':
        form = ClubForm(request.POST, request.FILES)
        formset = ClubCelluleFormSet(request.POST, prefix='club')
        
        if form.is_valid() and formset.is_valid():
            
            # --- VALIDATION : AU MOINS UNE CELLULE ---
            # On parcourt les formulaires pour voir s'il y en a au moins un rempli et non supprimé
            has_cellule = any(
                f.cleaned_data and not f.cleaned_data.get('DELETE', False) 
                for f in formset
            )

            if not has_cellule:
                # ERREUR : Aucune cellule trouvée
                messages.error(request, "Erreur : Vous devez ajouter au moins une cellule pour créer ce club.")
                return render(request, 'clubs/club_form.html', {
                    'form': form,
                    'formset': formset
                })

            # --- SI OK : On sauvegarde ---
            club = form.save()
            cellules = formset.save(commit=False)
            for cellule in cellules:
                cellule.club = club
                cellule.save()
            formset.save_m2m()
            return redirect('gestion_club_event')

    else:
        form = ClubForm()
        formset = ClubCelluleFormSet(queryset=Cellule.objects.none(), prefix='club')

    return render(request, 'clubs/club_form.html', {
        'form': form,
        'formset': formset
    })





def club_update(request, pk):
    club = get_object_or_404(Club, pk=pk)

    CelluleFormSet = inlineformset_factory(
        Club,
        Cellule,
        form=CelluleForm,
        extra=1,        # permet ajouter une cellule
        can_delete=True
    )

    if request.method == 'POST':
        form = ClubForm(request.POST, request.FILES, instance=club)
        formset = CelluleFormSet(request.POST, instance=club)

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('gestion_club_event')

    else:
        form = ClubForm(instance=club)
        formset = CelluleFormSet(instance=club)

    return render(request, 'clubs/club_update.html', {
        'club': club,
        'form': form,
        'formset': formset
    })


def club_delete(request, pk):
    club = get_object_or_404(Club, pk=pk)
    if request.method == 'POST':
        club.delete()
        return redirect('gestion_club_event')
    return render(request, 'clubs/confirm_delete.html', {'object': club, 'type': 'Club'})

# ---------- CRUD Event ----------
# Assure-toi d'avoir cet import en haut du fichier
def event_create(request):
    # On définit le formset
    EventCelluleFormSet = inlineformset_factory(
        Event, Cellule, form=CelluleForm, extra=1, can_delete=True
    )

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        formset = EventCelluleFormSet(request.POST, prefix='event')

        if form.is_valid() and formset.is_valid():
            
            # --- VALIDATION : AU MOINS UNE CELLULE ---
            has_cellule = any(
                f.cleaned_data and not f.cleaned_data.get('DELETE', False) 
                for f in formset
            )

            if not has_cellule:
                # ERREUR : Aucune cellule trouvée
                messages.error(request, "Erreur : Vous devez ajouter au moins une cellule pour créer cet événement.")
                return render(request, 'clubs/event_form.html', {
                    'form': form,
                    'formset': formset
                })

            # --- SI OK : On sauvegarde ---
            event = form.save()
            cellules = formset.save(commit=False)
            for cellule in cellules:
                cellule.event = event
                # Rappel : On ne lie pas au club pour garder l'indépendance
                cellule.save()

            return redirect('gestion_club_event')

    else:
        form = EventForm()
        formset = EventCelluleFormSet(queryset=Cellule.objects.none(), prefix='event')

    return render(request, 'clubs/event_form.html', {
        'form': form,
        'formset': formset
    })

def event_update(request, pk):
    event = get_object_or_404(Event, pk=pk)

    CelluleFormSet = inlineformset_factory(
        Event,
        Cellule,
        form=CelluleForm,
        extra=1,
        can_delete=True
    )

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        formset = CelluleFormSet(request.POST, instance=event)

        if form.is_valid() and formset.is_valid():
            event_saved = form.save()
            
            # 1. D'abord on appelle save(commit=False). 
            # C'est CETTE ligne qui remplit la liste 'deleted_objects'.
            cellules = formset.save(commit=False)

            # 2. Maintenant que la liste existe, on supprime manuellement les éléments cochés
            for obj in formset.deleted_objects:
                obj.delete()

            # 3. Ensuite, on sauvegarde les cellules restantes (nouvelles ou modifiées)
            for cellule in cellules:
                cellule.event = event_saved
                # Note : On ne lie PLUS la cellule au club ici (Indépendance stricte)
                cellule.save()
            
            return redirect('gestion_club_event')

    else:
        form = EventForm(instance=event)
        formset = CelluleFormSet(instance=event)

    return render(request, 'clubs/event_update.html', {
        'event': event,
        'form': form,
        'formset': formset,
        'readonly_cellules': False
    })

def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if request.method == 'POST':
        event.delete()
        return redirect('gestion_club_event')
    return render(request, 'clubs/confirm_delete.html', {'object': event, 'type': 'Event'})
