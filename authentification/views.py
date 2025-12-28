# authentification/views.py
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from authentification.forms import UserEditForm
from clubs.models import Club, Event
from .models import Profil
from recrutement.models import Annonce


# -------------------------
# HOMEPAGE
# -------------------------
def home(request):
    annonces = Annonce.objects.filter(
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    )

    events = Event.objects.all().order_by('-date')  # afficher les plus récents d’abord
    clubs = Club.objects.all().order_by('nom')  # <-- on récupère les clubs

    return render(request, 'authentification/home.html', {
        'annonces': annonces,
        'events': events,
        'clubs': clubs  
    })


# -------------------------
# LOGIN
# -------------------------
def signin(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)

        if not user:
            messages.error(request, 'Identifiants incorrects')
            return redirect('signin')

        # Login OK
        login(request, user)

        # Vérifier que le profil existe
        profil, created = Profil.objects.get_or_create(user=user)

        # Redirections selon rôle
        if profil.profil == 'admin':
            return redirect('admin_dashboard')

        elif profil.profil == 'president':
            return redirect('president_dashboard')

        elif profil.profil == 'chef_cellule':
            return redirect('chef_dashboard')

        elif profil.profil == 'membre':
            return redirect('membre_dashboard')

        return redirect('home')

    return render(request, 'authentification/signin.html')


# -------------------------
# LOGOUT
# -------------------------
@login_required
def signout(request):
    logout(request)
    return redirect('home')


# -------------------------
# ESPACE ADMIN
# -------------------------
@login_required
def admin_dashboard(request):
    annonces = Annonce.objects.all().order_by('-created_at')
    return render(request, 'authentification/admin_dashboard.html', {'annonces': annonces})


# # -------------------------
# # ESPACE PRESIDENT
# # -------------------------
# @login_required
# def president_dashboard(request):
#     return render(request, 'authentification/president_dashboard.html')


# # -------------------------
# # ESPACE CHEF DE CELLULE
# # -------------------------
# @login_required
# def chef_dashboard(request):
#     return render(request, 'authentification/chef_dashboard.html')


# # -------------------------
# # ESPACE MEMBRE
# # -------------------------
# @login_required
# def membre_dashboard(request):
#     return render(request, 'authentification/membre_dashboard.html')


# -------------------------
# ESPACE PRESIDENT
# -------------------------
@login_required
def president_dashboard(request):
    user = request.user
    
    # 1. Récupérer les CLUBS présidés par cet utilisateur
    # On précharge les cellules liées pour optimiser l'affichage
    my_clubs = user.preside_clubs.prefetch_related('cellules').all()
    
    # 2. Récupérer les ÉVÉNEMENTS (indépendants) présidés par cet utilisateur
    my_events = user.events_president.prefetch_related('cellules').all()

    context = {
        'my_clubs': my_clubs,
        'my_events': my_events,
    }
    return render(request, 'authentification/president_dashboard.html', context)


# -------------------------
# ESPACE CHEF DE CELLULE
# -------------------------
@login_required
def chef_dashboard(request):
    user = request.user

    # Le chef gère des CELLULES.
    # Ces cellules peuvent appartenir à un Club OU à un Event.
    # On utilise select_related pour le club/event (parents) et prefetch_related pour les membres (enfants)
    my_cellules = user.chef_cellules.select_related('club', 'event').prefetch_related('membres').all()

    context = {
        'my_cellules': my_cellules
    }
    return render(request, 'authentification/chef_dashboard.html', context)


# -------------------------
# ESPACE MEMBRE
# -------------------------
@login_required
def membre_dashboard(request):
    user = request.user

    # Le membre appartient à des CELLULES.
    # On veut voir le nom de la cellule, le club/event associé et qui est le chef.
    my_participations = user.membres_cellule.select_related('club', 'event', 'chef').all()
    
    # Optionnel : récupérer les annonces récentes si tu veux les afficher au membre
    recent_annonces = Annonce.objects.filter(
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    ).order_by('-created_at')[:5]

    context = {
        'my_participations': my_participations,
        'recent_annonces': recent_annonces
    }
    return render(request, 'authentification/membre_dashboard.html', context)

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User

from .models import Profil
from clubs.models import Cellule


@login_required
def gestion_utilisateurs(request):

    def grouper_utilisateurs(profils, role):
        data = {
            "clubs": {},
            "events_sans_club": {}
        }

        for profil in profils:
            user = profil.user

            # ==== PRESIDENTS ====
            if role == 'president':
                clubs = user.preside_clubs.all()
                events = user.events_president.all()

            # ==== CHEFS ====
            elif role == 'chef_cellule':
                cellules = user.chef_cellules.all()
                clubs = [c.club for c in cellules if c.club]
                events = [c.event for c in cellules if c.event]

            # ==== MEMBRES ====
            else:
                cellules = user.membres_cellule.all()
                clubs = [c.club for c in cellules if c.club]
                events = [c.event for c in cellules if c.event]

            # ---- CLUBS ----
            for club in set(clubs):
                if club not in data["clubs"]:
                    data["clubs"][club] = []

                data["clubs"][club].append(user)

            # ---- EVENTS ----
            for event in set(events):
                if event.club:
                    # event lié à un club → reste dans le club
                    if event.club not in data["clubs"]:
                        data["clubs"][event.club] = []
                    if user not in data["clubs"][event.club]:
                        data["clubs"][event.club].append(user)
                else:
                    # event sans club
                    if event not in data["events_sans_club"]:
                        data["events_sans_club"][event] = []
                    data["events_sans_club"][event].append(user)

        return data

    presidents = Profil.objects.filter(profil='president').select_related('user')
    chefs = Profil.objects.filter(profil='chef_cellule').select_related('user')
    membres = Profil.objects.filter(profil='membre').select_related('user')

    context = {
        "presidents_groupes": grouper_utilisateurs(presidents, 'president'),
        "chefs_groupes": grouper_utilisateurs(chefs, 'chef_cellule'),
        "membres_groupes": grouper_utilisateurs(membres, 'membre'),
    }

    return render(request, 'authentification/gestion_utilisateurs.html', context)

@login_required
def desactiver_utilisateur(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if user.is_superuser:
        messages.error(request, "Impossible de modifier un super administrateur.")
        return redirect('gestion_utilisateurs')

    # Inversion du statut (Actif <-> Inactif)
    user.is_active = not user.is_active
    user.save()

    if user.is_active:
        messages.success(request, f"{user.get_full_name()} a été réactivé.")
    else:
        # === C'EST ICI QUE TU AJOUTES LA LOGIQUE DE NETTOYAGE ===
        
        # 1. S'il était PRÉSIDENT de clubs, on libère le poste
        # (update met le champ à NULL pour tous les clubs concernés)
        clubs_presides = Club.objects.filter(president=user)
        count_clubs = clubs_presides.count()
        clubs_presides.update(president=None)

        # 2. S'il était CHEF de cellules, on libère le poste
        cellules_dirigees = Cellule.objects.filter(chef=user)
        count_cellules = cellules_dirigees.count()
        cellules_dirigees.update(chef=None)

        # On adapte le message pour confirmer que le poste est libre
        msg_detail = ""
        if count_clubs > 0 or count_cellules > 0:
            msg_detail = f" Il a été retiré de {count_clubs} club(s) et {count_cellules} cellule(s)."
        
        messages.warning(request, f"{user.get_full_name()} a été désactivé.{msg_detail}")

    return redirect('gestion_utilisateurs')

@login_required
def modifier_utilisateur(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Utilisateur modifié avec succès.")
            return redirect('gestion_utilisateurs')
    else:
        form = UserEditForm(instance=user)

    return render(request, 'authentification/modifier_utilisateur.html', {
        'form': form,
        'user_modif': user
    })

@login_required
def supprimer_utilisateur(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if not user.is_superuser: # Sécurité
        user.delete()
        messages.success(request, "Utilisateur supprimé définitivement.")
    return redirect('gestion_utilisateurs')