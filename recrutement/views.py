from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.mail import send_mail
from collections import defaultdict
import random
import string

# Assure-toi que les imports correspondent bien à tes fichiers
from .models import Annonce, Candidature
from .forms import AnnonceForm, CandidatureForm
from authentification.models import Profil
from clubs.models import Cellule, Event

# ==========================================
# 1. AJAX POUR CHARGER LES CELLULES
# ==========================================
@login_required
def load_cells_events(request):
    club_id = request.GET.get('club')
    event_id = request.GET.get('event')

    data = {
        'cellules': [],
        'events': []
    }

    if club_id:
        cellules = Cellule.objects.filter(club_id=club_id).values('id', 'nom')
        events = Event.objects.filter(club_id=club_id).values('id', 'titre')
        data['cellules'] = list(cellules)
        data['events'] = list(events)
    elif event_id:
        cellules = Cellule.objects.filter(event_id=event_id).values('id', 'nom')
        data['cellules'] = list(cellules)

    return JsonResponse(data)


# ==========================================
# 2. GESTION ANNONCE (CRÉATION ET MODIFICATION)
# ==========================================
@login_required
def gerer_annonce(request, id=None):
    # Vérification que l'utilisateur est admin
    try:
        profil = Profil.objects.get(user=request.user).profil
    except Profil.DoesNotExist:
        return redirect('home')
        
    if profil != 'admin':
        return redirect('home')

    # Si un ID est fourni, on récupère l'annonce (Mode Modification)
    if id:
        annonce = get_object_or_404(Annonce, id=id)
        titre_page = "Modifier l'annonce"
    else:
        # Sinon, nouvelle annonce (Mode Création)
        annonce = None
        titre_page = "Créer une annonce"

    if request.method == 'POST':
        form = AnnonceForm(request.POST, request.FILES, instance=annonce)
        if form.is_valid():
            obj = form.save(commit=False)
            
            # Si c'est une création, on assigne le publisher
            if not annonce:
                obj.publisher = request.user
                obj.publisher_type = 'admin'
            
            obj.save()
            form.save_m2m() # Important pour sauvegarder les relations ManyToMany
            
            if id:
                messages.success(request, "Annonce modifiée avec succès !")
            else:
                messages.success(request, "Annonce créée avec succès !")
            
            return redirect('admin_dashboard') 
        else:
            error_text = "; ".join([f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()])
            messages.error(request, f"Erreur dans le formulaire : {error_text}")
    else:
        form = AnnonceForm(instance=annonce)

    return render(request, 'recrutement/create_annonce.html', {
        'form': form, 
        'titre_page': titre_page
    })


# ==========================================
# 3. POSTULER (MISE À JOUR INTELLIGENTE)
# ==========================================
def postuler(request, annonce_id):
    # 1. On récupère l'annonce
    annonce = get_object_or_404(Annonce, pk=annonce_id)
    club_concerne = annonce.club if hasattr(annonce, 'club') else None
    event_concerne = annonce.event if hasattr(annonce, 'event') else None

    # 2. ANALYSE DES CIBLES
    raw_targets = str(annonce.target_postes).lower() if annonce.target_postes else ""
    is_offre_membre = 'membre' in raw_targets
    is_offre_responsable = 'chef' in raw_targets or 'president' in raw_targets or 'responsable' in raw_targets

    # =========================================================
    # 3. LE FILTRE À L'ENTRÉE (GET - AVANT D'AFFICHER LA PAGE)
    # =========================================================

    # A. VISITEURS (NON CONNECTÉS)
    if not request.user.is_authenticated:
        # CLUB : Si l'annonce ne propose PAS 'membre' (c'est une offre Chef/Président pure)
        # On bloque immédiatement les inconnus.
        if club_concerne and not is_offre_membre:
            messages.error(request, "Action refusée : Ce poste nécessite d'être déjà membre connecté.")
            return redirect('home')

    # B. UTILISATEURS CONNECTÉS
    if request.user.is_authenticated:
        
        # 1. ANTI-CUMUL
        if club_concerne:
            if Cellule.objects.filter(club=club_concerne, chef=request.user).exists():
                messages.error(request, "Refusé : Vous êtes déjà Chef de cellule dans ce club.")
                return redirect('home')
            if hasattr(club_concerne, 'president') and club_concerne.president == request.user:
                messages.error(request, "Refusé : Vous êtes déjà le Président de ce club.")
                return redirect('home')

        if event_concerne:
            if hasattr(event_concerne, 'president') and event_concerne.president == request.user:
                messages.error(request, "Refusé : Vous êtes déjà le Président de cet événement.")
                return redirect('home')
            if Cellule.objects.filter(event=event_concerne, chef=request.user).exists():
                messages.error(request, "Refusé : Vous êtes déjà Chef de cellule pour cet événement.")
                return redirect('home')

        # 2. HIÉRARCHIE CLUB
        if club_concerne:
            est_membre = request.user in club_concerne.membres.all()

            if not est_membre:
                # NOUVEAU : Si l'annonce est Chef/Président pur -> BLOCAGE
                if not is_offre_membre:
                    messages.error(request, "Accès refusé : Réservé aux membres actuels (Promotion interne).")
                    return redirect('home')
            else:
                # MEMBRE : Si l'annonce est Membre pur -> BLOCAGE
                if not is_offre_responsable:
                    messages.info(request, "Vous êtes déjà membre du club.")
                    return redirect('home')

        # 3. CANDIDATURE EN COURS
        if Candidature.objects.filter(username=request.user.username, annonce=annonce).exclude(status__in=['acceptee', 'refusee']).exists():
             messages.warning(request, "Vous avez déjà une candidature en cours.")
             return redirect('home')

    # =========================================================
    # 4. TRAITEMENT DU FORMULAIRE (POST - LA CORRECTION EST ICI)
    # =========================================================
    if request.method == 'POST':
        try:
            user_obj = request.user if request.user.is_authenticated else None
            form = CandidatureForm(request.POST, annonce=annonce, user=user_obj)
        except TypeError:
            form = CandidatureForm(request.POST, annonce=annonce)

        if form.is_valid():
            profil_choisi = form.cleaned_data.get('profil_souhaite')
            
            # --- SÉCURITÉ RENFORCÉE ---
            if club_concerne:
                
                # CAS 1 : VISITEUR NON CONNECTÉ
                # C'est ici que ça manquait ! Si un anonyme choisit Chef ou Président -> BLOQUÉ
                if not request.user.is_authenticated:
                    if profil_choisi in ['chef_cellule', 'president']:
                        messages.error(request, "Action refusée : Vous devez être membre (et connecté) pour postuler à ce poste.")
                        return redirect('home') # Retour accueil direct

                # CAS 2 : UTILISATEUR CONNECTÉ
                else:
                    est_membre = request.user in club_concerne.membres.all()
                    
                    # Nouveau qui essaie d'être Chef/Président -> BLOQUÉ
                    if not est_membre and profil_choisi in ['chef_cellule', 'president']:
                        messages.error(request, "Refusé : Vous devez d'abord être Membre pour prétendre à ce poste.")
                        return redirect('home')

                    # Membre qui essaie d'être Membre -> BLOQUÉ
                    if est_membre and profil_choisi == 'membre':
                        messages.error(request, "Erreur : Vous êtes déjà membre.")
                        return redirect('home')

            # Sauvegarde
            candidature = form.save(commit=False)
            candidature.annonce = annonce 
            if club_concerne: candidature.club = club_concerne
            if event_concerne: candidature.event = event_concerne
            
            if request.user.is_authenticated:
                candidature.prenom = request.user.first_name
                candidature.nom = request.user.last_name
                candidature.email = request.user.email
                candidature.username = request.user.username
            
            candidature.save()
            messages.success(request, "Votre candidature a été envoyée avec succès !")
            return redirect('home')
        else:
             messages.error(request, "Veuillez corriger les erreurs.")
    else:
        try:
            user_obj = request.user if request.user.is_authenticated else None
            form = CandidatureForm(annonce=annonce, user=user_obj)
        except TypeError:
            form = CandidatureForm(annonce=annonce)

    return render(request, 'recrutement/postuler.html', {
        'form': form,
        'annonce': annonce
    })

# ==========================================
# 4. ADMIN VIEW CANDIDATURES
# ==========================================
@login_required
def admin_candidatures(request, annonce_id):
    annonce = get_object_or_404(Annonce, id=annonce_id)

    presidents = Candidature.objects.filter(
        annonce=annonce, profil_souhaite='president'
    ).order_by('-created_at')

    chefs = Candidature.objects.filter(
        annonce=annonce, profil_souhaite='chef_cellule'
    ).order_by('cellule__nom', '-created_at')

    chefs_grouped = defaultdict(list)
    for cand in chefs:
        if cand.cellule:
            chefs_grouped[cand.cellule.nom].append(cand)
        else:
            chefs_grouped["Sans cellule"].append(cand)

    membres = Candidature.objects.filter(
        annonce=annonce, profil_souhaite='membre'
    ).order_by('cellule__nom', '-created_at')

    membres_grouped = defaultdict(list)
    for cand in membres:
        if cand.cellule:
            membres_grouped[cand.cellule.nom].append(cand)
        else:
            membres_grouped["Sans cellule"].append(cand)

    context = {
        'annonce': annonce,
        'presidents': presidents,
        'chefs_grouped': dict(chefs_grouped),
        'membres_grouped': dict(membres_grouped),
    }

    return render(request, 'recrutement/admin_candidatures.html', context)


# ==========================================
# 5. TRAITER CANDIDATURE (INTELLIGENT)
# ==========================================
@login_required
def traiter_candidature(request, cand_id, action):
    cand = get_object_or_404(Candidature, id=cand_id)
    
    try:
        profil_admin = Profil.objects.get(user=request.user)
    except Profil.DoesNotExist:
        return redirect('home')

    if profil_admin.profil != 'admin':
        return redirect('home')

    # === SI ADMIN ACCEPTE ============================
    if action == 'accepter':

        # --- 1. Vérifications unicité ---
        if cand.profil_souhaite == 'president':
            if cand.club and cand.club.president:
                cand.status = 'refusee'
                cand.save()
                messages.error(request, f"Le club {cand.club.nom} a déjà un président.")
                return redirect('admin_candidatures', annonce_id=cand.annonce.id)
            
            if cand.event and cand.event.president:
                cand.status = 'refusee'
                cand.save()
                messages.error(request, "Cet évènement a déjà un président.")
                return redirect('admin_candidatures', annonce_id=cand.annonce.id)

        if cand.profil_souhaite == 'chef_cellule':
            if cand.cellule and cand.cellule.chef:
                cand.status = 'refusee'
                cand.save()
                messages.error(request, f"La cellule {cand.cellule.nom} a déjà un chef.")
                return redirect('admin_candidatures', annonce_id=cand.annonce.id)

        # --- 2. CRÉATION OU RÉCUPÉRATION DU USER ---
        user, created = User.objects.get_or_create(
            username=cand.username,
            defaults={
                'email': cand.email,
                'first_name': cand.prenom,
                'last_name': cand.nom,
            }
        )
        
        # Mise à jour des infos
        user.email = cand.email
        user.first_name = cand.prenom
        user.last_name = cand.nom
        
        # === GESTION INTELLIGENTE DU MOT DE PASSE ===
        msg_mdp = ""
        
        if created:
            if cand.password:
                user.set_password(cand.password)
            else:
                user.set_password('Defaut1234!') 
            user.save()
            msg_mdp = "Mot de passe : Celui que vous avez choisi lors de l'inscription."
        else:
            user.save()
            msg_mdp = "Mot de passe : Votre mot de passe habituel (inchangé)."

        # --- 3. Affectation du rôle ---
        if cand.profil_souhaite == 'president':
            if cand.club:
                cand.club.president = user
                cand.club.save()
                for event in cand.club.events.all():
                    event.president = user
                    event.save()
            elif cand.event:
                cand.event.president = user
                cand.event.save()

        if cand.profil_souhaite == 'chef_cellule' and cand.cellule:
            cand.cellule.chef = user
            cand.cellule.save()
            if cand.cellule.club:
                for event in cand.cellule.club.events.all():
                    event.chefs.add(user)
            if cand.cellule.event:
                 cand.cellule.event.chefs.add(user)

        # --- 4. Ajouter comme membre ---
        if cand.club:
            cand.club.membres.add(user)
        if cand.cellule:
            cand.cellule.membres.add(user)

        # --- 5. Profil utilisateur ---
        Profil.objects.update_or_create(
            user=user,
            defaults={'profil': cand.profil_souhaite}
        )

        # --- 6. Email d’acceptation ---
        send_mail(
            'Candidature acceptée',
            f"""Bonjour {cand.prenom},

Félicitations ! Votre candidature pour le poste de {cand.profil_souhaite.replace('_',' ')} a été acceptée !

Vous pouvez désormais vous connecter avec :
- Username : {cand.username}
- {msg_mdp}

Rendez-vous sur la plateforme.
""",
            'admin@club.com',
            [cand.email],
            fail_silently=True
        )

        cand.status = 'acceptee'

    # === SI ADMIN REFUSE ============================
    else:
        cand.status = 'refusee'
        send_mail(
            'Candidature refusée',
            f"Bonjour {cand.prenom}, votre candidature pour {cand.profil_souhaite} a été refusée.",
            'admin@club.com',
            [cand.email],
            fail_silently=True
        )

    # --- Finalisation ---
    cand.processed_at = timezone.now()
    cand.processed_by = request.user
    cand.save()

    return redirect('admin_candidatures', annonce_id=cand.annonce.id)


# ==========================================
# 6. SUPPRIMER ANNONCE
# ==========================================
@login_required
def delete_annonce(request, annonce_id):
    annonce = get_object_or_404(Annonce, id=annonce_id)
    
    try:
        profil_admin = Profil.objects.get(user=request.user)
    except Profil.DoesNotExist:
        messages.error(request, "Accès refusé.")
        return redirect('home')

    if profil_admin.profil != 'admin':
        messages.error(request, "Vous n'avez pas la permission de supprimer cette annonce.")
        return redirect('admin_dashboard') 
    
    annonce.delete()
    messages.success(request, "Annonce supprimée avec succès !")
    
    return redirect('admin_dashboard')