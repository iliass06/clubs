from django.shortcuts import render, get_object_or_404, redirect
from .models import Cellule, Club, Event
from .forms import CelluleForm, ClubCelluleFormSet, ClubForm, EventCelluleFormSet, EventForm

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
def club_create(request):
    if request.method == 'POST':
        form = ClubForm(request.POST, request.FILES)
        formset = ClubCelluleFormSet(request.POST, prefix='club')
        if form.is_valid() and formset.is_valid():
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



from django.forms import inlineformset_factory

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
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        formset = EventCelluleFormSet(request.POST, prefix='event')

        if form.is_valid():
            event = form.save()

            # 🔹 CAS 1 : Event lié à un club → reprendre les cellules du club
            if event.club:
                cellules_club = Cellule.objects.filter(club=event.club)

                for cellule in cellules_club:
                    cellule.event = event
                    cellule.save()

            # 🔹 CAS 2 : Event sans club → création libre de cellules
            else:
                if formset.is_valid():
                    cellules = formset.save(commit=False)
                    for cellule in cellules:
                        cellule.event = event
                        cellule.save()

            return redirect('gestion_club_event')

    else:
        form = EventForm()
        formset = EventCelluleFormSet(
            queryset=Cellule.objects.none(),
            prefix='event'
        )

    return render(request, 'clubs/event_form.html', {
        'form': form,
        'formset': formset
    })





from django.forms import inlineformset_factory

def event_update(request, pk):
    event = get_object_or_404(Event, pk=pk)

    CelluleFormSet = inlineformset_factory(
        Event,
        Cellule,
        form=CelluleForm,
        extra=0,
        can_delete=True
    )

    # 🔒 EVENT LIÉ À UN CLUB → PAS DE MODIFICATION DES CELLULES
    if event.club:
        form = EventForm(request.POST or None, request.FILES or None, instance=event)

        if request.method == 'POST' and form.is_valid():
            form.save()
            return redirect('gestion_club_event')

        return render(request, 'clubs/event_update.html', {
            'event': event,
            'form': form,
            'club_cellules': event.club.cellules.all(),
            'readonly_cellules': True
        })

    # ✏️ EVENT SANS CLUB → CELLULES MODIFIABLES
    else:
        form = EventForm(request.POST or None, request.FILES or None, instance=event)
        formset = CelluleFormSet(request.POST or None, instance=event)

        if request.method == 'POST' and form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('gestion_club_event')

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
