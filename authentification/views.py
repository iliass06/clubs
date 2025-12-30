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
@login_required
def membre_dashboard(request):
    user = request.user

    # --- PARTIE 1 : RÉCUPÉRATION DE TOUS LES RÔLES POSSIBLES ---
    
    # Présidences
    mes_presidences_clubs = user.preside_clubs.all()
    mes_presidences_events = user.events_president.all()
    
    # Responsabilités (Chefs)
    mes_cellules_chef = user.chef_cellules.select_related('club', 'event').all()
    
    # Adhésions simples (Membres)
    mes_cellules_membre = user.membres_cellule.select_related('club', 'event').all()
    mes_clubs_membre = user.membres_club.all()


    # --- PARTIE 2 : HISTORIQUE AVEC LOGIQUE "ACTIF/RETIRÉ" ---
    # On trie du plus récent au plus ancien pour appliquer la logique "Premier arrivé = Actif"
    candidatures_qs = Candidature.objects.filter(username=user.username).select_related('annonce', 'club', 'event', 'cellule').order_by('-created_at')
    
    my_candidatures = []
    mandats_actifs_attribues = set() # Mémoire pour éviter les doublons actifs

    for cand in candidatures_qs:
        cand.etat_actuel = "-" 

        if cand.status == 'acceptee':
            
            # A. Identifier le contexte unique (Club X ou Event Y)
            contexte_key = "inconnu"
            if cand.club: contexte_key = f"club_{cand.club.id}"
            elif cand.event: contexte_key = f"event_{cand.event.id}"
            if cand.cellule: contexte_key += f"_cell_{cand.cellule.id}"

            # B. Nettoyer le profil (gestion des vides/espaces)
            raw_profil = str(cand.profil_souhaite).lower().strip()
            if not raw_profil or raw_profil == 'none': raw_profil = 'membre'

            # C. Déterminer le rôle théorique et vérifier la présence réelle en base
            role_key = "membre"
            est_present_db = False

            if 'president' in raw_profil:
                role_key = "president"
                if (cand.club and cand.club.president == user) or (cand.event and cand.event.president == user):
                    est_present_db = True
            elif 'chef' in raw_profil:
                role_key = "chef"
                if cand.cellule and cand.cellule.chef == user:
                    est_present_db = True
            else:
                role_key = "membre"
                if cand.club and user in cand.club.membres.all():
                    est_present_db = True
                elif cand.cellule and user in cand.cellule.membres.all():
                    est_present_db = True

            # D. Verdict final
            signature = f"{contexte_key}_{role_key}"

            if est_present_db:
                # Si l'user est physiquement dans le club
                if signature not in mandats_actifs_attribues:
                    # C'est la candidature la plus récente pour ce poste -> ACTIF
                    cand.etat_actuel = "Actif"
                    mandats_actifs_attribues.add(signature)
                else:
                    # On a déjà marqué ce poste comme actif plus haut (donc plus récent) -> RETIRÉ
                    cand.etat_actuel = "Retiré"
            else:
                # L'user n'est plus dans la base -> RETIRÉ
                cand.etat_actuel = "Retiré"

        my_candidatures.append(cand)

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

    def grouper_utilisateurs(profils, role):
        data = {
            "clubs": {},
            "events_sans_club": {}
        }

        for profil in profils:
            user = profil.user

            # =================================================
            # 1. LOGIQUE POUR LES PRÉSIDENTS
            # =================================================
            if role == 'president':
                # On récupère les clubs et events présidés
                clubs = user.preside_clubs.all()
                events = user.events_president.all()
                
                # Remplissage Clubs
                for club in clubs:
                    if club not in data["clubs"]: data["clubs"][club] = []
                    # Info inutile pour président, on met vide
                    data["clubs"][club].append({'user': user, 'info': ''})

                # Remplissage Events sans club
                for event in events:
                    if not event.club:
                        if event not in data["events_sans_club"]: data["events_sans_club"][event] = []
                        data["events_sans_club"][event].append({'user': user, 'info': ''})

            # =================================================
            # 2. LOGIQUE POUR LES CHEFS DE CELLULE
            # =================================================
            elif role == 'chef_cellule':
                cellules = user.chef_cellules.select_related('club', 'event').all()
                
                for cell in cellules:
                    # Gestion Clubs
                    if cell.club:
                        if cell.club not in data["clubs"]: data["clubs"][cell.club] = []
                        # Info = Nom de la cellule dirigée
                        data["clubs"][cell.club].append({'user': user, 'info': cell.nom})
                    
                    # Gestion Events sans club
                    elif cell.event and not cell.event.club:
                        evt = cell.event
                        if evt not in data["events_sans_club"]: data["events_sans_club"][evt] = []
                        data["events_sans_club"][evt].append({'user': user, 'info': cell.nom})

            # =================================================
            # 3. LOGIQUE POUR LES MEMBRES (Celle qui t'intéresse)
            # =================================================
            else:
                # On prend TOUS les clubs où il est membre (même sans cellule)
                clubs = user.membres_club.all()
                
                for club in clubs:
                    # On cherche s'il appartient à une cellule DANS CE CLUB
                    # On filtre les cellules du user qui appartiennent à ce club
                    user_cells_in_club = user.membres_cellule.filter(club=club)
                    
                    if user_cells_in_club.exists():
                        # S'il a des cellules, on les liste (ex: "Sponsoring, Media")
                        info_cellule = ", ".join([c.nom for c in user_cells_in_club])
                    else:
                        # S'il n'a pas de cellule, on affiche le tiret "-"
                        info_cellule = "-"
                    
                    if club not in data["clubs"]: data["clubs"][club] = []
                    data["clubs"][club].append({'user': user, 'info': info_cellule})

                # Idem pour les events sans club
                events = [c.event for c in user.membres_cellule.all() if c.event and not c.event.club]
                for evt in set(events):
                     if evt not in data["events_sans_club"]: data["events_sans_club"][evt] = []
                     # Pour les events, il est forcément dans une cellule s'il est membre_cellule
                     user_cells_in_event = user.membres_cellule.filter(event=evt)
                     info = ", ".join([c.nom for c in user_cells_in_event])
                     data["events_sans_club"][evt].append({'user': user, 'info': info})

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