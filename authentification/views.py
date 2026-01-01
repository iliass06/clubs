# authentification/views.py
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

# Imports des modèles
from clubs.models import Club, Event, Cellule
from .models import Profil
from recrutement.models import Annonce, Candidature

# Imports des formulaires
from authentification.forms import UserEditForm, SignUpForm


# -------------------------
# HOMEPAGE
# -------------------------
def home(request):
    annonces = Annonce.objects.filter(
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    )

    events = Event.objects.all().order_by('-date')
    clubs = Club.objects.all().order_by('nom')

    return render(request, 'authentification/home.html', {
        'annonces': annonces,
        'events': events,
        'clubs': clubs  
    })


# -------------------------
# INSCRIPTION (SIGNUP)
# -------------------------
def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('home')
    else:
        form = SignUpForm()

    return render(request, 'authentification/signup.html', {'form': form})


# -------------------------
# CONNEXION (SIGNIN)
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

        login(request, user)
        
        # 1. Gestion ADMIN (Reste séparé)
        try:
            profil = Profil.objects.get(user=user)
            if profil.profil == 'admin' or user.is_superuser:
                return redirect('admin_dashboard')
        except Profil.DoesNotExist:
            pass

        # 2. TOUS LES AUTRES -> Espace Utilisateur Unifié
        # Peu importe s'il est président, chef ou membre, il va au même endroit.
        return redirect('membre_dashboard')

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


# -------------------------
# ESPACE PRESIDENT
# -------------------------
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from recrutement.models import Candidature
from clubs.models import Cellule 

@login_required
def membre_dashboard(request):
    user = request.user

    # --- PARTIE 1 : RÉCUPÉRATION DES RÔLES ACTUELS ---
    mes_presidences_clubs = user.preside_clubs.all()
    mes_presidences_events = user.events_president.all()
    mes_cellules_chef = user.chef_cellules.select_related('club', 'event').all()
    mes_cellules_membre = user.membres_cellule.select_related('club', 'event').all()
    mes_clubs_membre = user.membres_club.all()

    # --- PARTIE 2 : HISTORIQUE INTELLIGENT ---
    # CORRECTION ICI : On utilise 'created_at' au lieu de 'date_created'
    candidatures_qs = Candidature.objects.filter(username=user.username).select_related('annonce', 'club', 'event', 'cellule').order_by('-created_at')
    
    my_candidatures = []
    postes_actifs_memoire = set() 

    for c in candidatures_qs:
        # Par défaut
        c.etat_visuel = c.get_status_display()
        c.css_class = "secondary" 
        
        if c.status == 'en_attente':
            c.css_class = "warning text-dark"
        elif c.status == 'refusee':
            c.css_class = "danger"

        elif c.status == 'acceptee':
            # 1. Vérification de la RÉALITÉ
            est_toujours_en_poste = False

            # Cas CLUB
            if c.club:
                if c.profil_souhaite == 'membre':
                    est_toujours_en_poste = c.club.membres.filter(pk=user.pk).exists()
                elif c.profil_souhaite == 'chef_cellule':
                    est_toujours_en_poste = Cellule.objects.filter(club=c.club, chef=user).exists()
                elif c.profil_souhaite == 'president':
                    est_toujours_en_poste = (c.club.president == user)

            # Cas EVENT
            elif c.event:
                if c.profil_souhaite == 'membre':
                    est_toujours_en_poste = Cellule.objects.filter(event=c.event, membres=user).exists()
                elif c.profil_souhaite == 'chef_cellule':
                    est_toujours_en_poste = Cellule.objects.filter(event=c.event, chef=user).exists()
                elif c.profil_souhaite == 'president':
                    est_toujours_en_poste = (c.event.president == user)

            # 2. Clé unique
            contexte_id = f"club_{c.club.id}" if c.club else f"event_{c.event.id}"
            unique_key = f"{contexte_id}_{c.profil_souhaite}"

            # 3. Verdict Visuel
            if est_toujours_en_poste:
                if unique_key not in postes_actifs_memoire:
                    c.etat_visuel = "Actif"
                    c.css_class = "success"
                    postes_actifs_memoire.add(unique_key)
                else:
                    c.etat_visuel = "Renouvellement / Archivé"
                    c.css_class = "secondary"
            else:
                c.etat_visuel = "Retiré / Ancien membre"
                c.css_class = "dark" 

        my_candidatures.append(c)

    context = {
        'mes_presidences_clubs': mes_presidences_clubs,
        'mes_presidences_events': mes_presidences_events,
        'mes_cellules_chef': mes_cellules_chef,
        'mes_cellules_membre': mes_cellules_membre,
        'mes_clubs_membre': mes_clubs_membre,
        'my_candidatures': my_candidatures
    }
    return render(request, 'authentification/membre_dashboard.html', context)

# -------------------------
# GESTION UTILISATEURS (ADMIN)
# -------------------------
@login_required
def gestion_utilisateurs(request):
    try:
        if request.user.profil.profil != 'admin':
            return redirect('home')
    except:
        return redirect('home')

    # --- 1. RÉCUPÉRATION DES RÔLES EXISTANTS ---
    
    # Présidents
    clubs_presidents = Club.objects.filter(president__isnull=False).select_related('president')
    events_presidents = Event.objects.filter(president__isnull=False).select_related('president')

    # Chefs de cellule
    chefs_cellules = Cellule.objects.filter(chef__isnull=False).select_related('chef', 'club', 'event')

    # Membres (Clubs et Events via cellules)
    clubs_list = Club.objects.prefetch_related('cellules__membres').all()
    events_list = Event.objects.prefetch_related('cellules__membres').all()


    # --- 2. CALCUL DES UTILISATEURS SANS RÔLE ---
    
    # On crée un ensemble (set) pour stocker les IDs de tous ceux qui sont OCCUPÉS
    ids_actifs = set()

    # On ajoute les Présidents
    for c in clubs_presidents: ids_actifs.add(c.president.id)
    for e in events_presidents: ids_actifs.add(e.president.id)
    
    # On ajoute les Chefs
    for chef in chefs_cellules: ids_actifs.add(chef.chef.id)
    
    # On ajoute les Membres de Clubs
    for c in clubs_list:
        for m in c.membres.all(): ids_actifs.add(m.id)
        
    # On ajoute les Membres d'Events
    for e in events_list:
        for cell in e.cellules.all():
            for m in cell.membres.all(): ids_actifs.add(m.id)

    # REQUÊTE FINALE : Tous les users SAUF ceux dans ids_actifs (et sauf les superadmins)
    users_sans_role = User.objects.exclude(id__in=ids_actifs).exclude(is_superuser=True).order_by('-date_joined')

    context = {
        'clubs_presidents': clubs_presidents,
        'events_presidents': events_presidents,
        'chefs_cellules': chefs_cellules,
        'clubs_list': clubs_list,
        'events_list': events_list,
        'users_sans_role': users_sans_role, # <--- La nouvelle liste
    }

    return render(request, 'authentification/gestion_utilisateurs.html', context)

# -------------------------
# DESACTIVER UTILISATEUR (RETIRER LES DROITS) - MODIFIÉ
# -------------------------
@login_required
def desactiver_utilisateur(request, user_id, action):
    user = get_object_or_404(User, id=user_id)

    if user.is_superuser:
        messages.error(request, "Impossible de modifier un super administrateur.")
        return redirect('gestion_utilisateurs')

    # --- 1. ACTION : RÉTROGRADER (Pour Présidents / Chefs) ---
    if action == 'retrograder':
        Club.objects.filter(president=user).update(president=None)
        Event.objects.filter(president=user).update(president=None)
        Cellule.objects.filter(chef=user).update(chef=None)
        for evt in Event.objects.filter(chefs=user):
            evt.chefs.remove(user)

        try:
            profil = Profil.objects.get(user=user)
            profil.profil = 'membre'
            profil.save()
        except Profil.DoesNotExist:
            pass
            
        messages.warning(request, f"{user.get_full_name()} n'est plus Responsable, mais il reste Membre du club.")

    # --- 2. ACTION : EXCLURE (Pour Membres) ---
    elif action == 'exclure':
        # Nettoyage responsabilités
        Club.objects.filter(president=user).update(president=None)
        Event.objects.filter(president=user).update(president=None)
        Cellule.objects.filter(chef=user).update(chef=None)
        for evt in Event.objects.filter(chefs=user):
            evt.chefs.remove(user)

        # Nettoyage adhésions
        for club in Club.objects.filter(membres=user):
            club.membres.remove(user)
        for cellule in Cellule.objects.filter(membres=user):
            cellule.membres.remove(user)
            
        try:
            profil = Profil.objects.get(user=user)
            profil.profil = 'membre'
            profil.save()
        except Profil.DoesNotExist:
            pass

        # === CORRECTION ICI : messages.error au lieu de messages.danger ===
        messages.error(request, f"{user.get_full_name()} a été retiré totalement du club (Responsabilités et Adhésion).")

    return redirect('gestion_utilisateurs')

# -------------------------
# MODIFIER UTILISATEUR
# -------------------------
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


# -------------------------
# SUPPRIMER UTILISATEUR (SUPPRESSION DEFINITIVE DU COMPTE)
# -------------------------
@login_required
def supprimer_utilisateur(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if not user.is_superuser: # Sécurité
        # user.delete() supprime l'enregistrement de la base de données auth_user.
        # Cela supprime le compte définitivement et cascade sur le Profil.
        user.delete()
        messages.success(request, "Le compte utilisateur a été supprimé définitivement.")
    return redirect('gestion_utilisateurs')

# Ajoute ces imports en haut si ce n'est pas déjà fait

@login_required
def quitter_poste(request, type_objet, id_objet, role):
    user = request.user
    
    # 1. CAS CLUB
    if type_objet == 'club':
        obj = get_object_or_404(Club, id=id_objet)
        
        # A. Démissionner de la Présidence
        if role == 'president':
            if obj.president == user:
                obj.president = None
                obj.save()
                messages.success(request, f"Vous avez démissionné de la présidence du club {obj.nom}.")

        # B. Quitter le Club (Règle spéciale : Nettoyage complet)
        elif role == 'membre':
            # 1. Retirer de la liste des membres du club
            if user in obj.membres.all():
                obj.membres.remove(user)
            
            # 2. Si l'user était aussi Président -> On le retire
            if obj.president == user:
                obj.president = None
                obj.save()
            
            # 3. Retirer de TOUTES les cellules de ce club (Chef ou Membre)
            cellules_club = Cellule.objects.filter(club=obj)
            for cell in cellules_club:
                if cell.chef == user:
                    cell.chef = None
                    cell.save()
                if user in cell.membres.all():
                    cell.membres.remove(user)
            
            messages.success(request, f"Vous avez quitté le club {obj.nom} et tous les postes associés.")

    # 2. CAS EVENT
    elif type_objet == 'event':
        obj = get_object_or_404(Event, id=id_objet)
        
        if role == 'president':
            if obj.president == user:
                obj.president = None
                obj.save()
                messages.success(request, f"Vous avez démissionné de l'événement {obj.titre}.")

    # 3. CAS CELLULE
    elif type_objet == 'cellule':
        obj = get_object_or_404(Cellule, id=id_objet)
        
        if role == 'chef':
            if obj.chef == user:
                obj.chef = None
                obj.save()
                messages.success(request, f"Vous n'êtes plus chef de la cellule {obj.nom}.")
        
        elif role == 'membre':
            if user in obj.membres.all():
                obj.membres.remove(user)
                messages.success(request, f"Vous avez quitté la cellule {obj.nom}.")

    return redirect('membre_dashboard')