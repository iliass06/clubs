from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.mail import send_mail
from collections import defaultdict
from django.urls import reverse
import random
import string

from .models import Annonce, Candidature
from .forms import AnnonceForm, CandidatureForm
from authentification.models import Profil
from clubs.models import Cellule, Event

# ==========================================
# 1. AJAX (Inchangé)
# ==========================================
@login_required
def load_cells_events(request):
    club_id = request.GET.get('club')
    event_id = request.GET.get('event')

    # --- MODIFICATION ICI : On ajoute 'club_id' pour savoir qui est le parent ---
    events_qs = Event.objects.all().values('id', 'titre', 'club_id')
    
    cellules = Cellule.objects.none()
    
    if club_id:
        cellules = cellules | Cellule.objects.filter(club_id=club_id)
        # On garde le filtre, mais on inclut toujours 'club_id'
        events_qs = Event.objects.filter(club_id=club_id).values('id', 'titre', 'club_id')
    
    if event_id:
        cellules = cellules | Cellule.objects.filter(event_id=event_id)

    return JsonResponse({
        'cellules': list(cellules.distinct().values('id', 'nom')),
        'events': list(events_qs)
    })

# ==========================================
# 2. GESTION ANNONCE (Inchangé)
# ==========================================
# recrutement/views.py

@login_required
def gerer_annonce(request, id=None):
    try:
        profil = Profil.objects.get(user=request.user).profil
    except Profil.DoesNotExist:
        return redirect('home')
        
    if profil != 'admin':
        return redirect('home')

    if id:
        annonce = get_object_or_404(Annonce, id=id)
        titre_page = "Modifier l'annonce"
    else:
        annonce = None
        titre_page = "Créer une annonce"

    if request.method == 'POST':
        form = AnnonceForm(request.POST, request.FILES, instance=annonce)
        if form.is_valid():
            obj = form.save(commit=False)
            
            # --- LOGIQUE DE PRIORITÉ (Ce que tu as demandé) ---
            
            if obj.event:
                # CAS 1 : C'est un Event (qu'il soit lié à un club ou non)
                # On détache le club direct de l'annonce pour que la candidature
                # ne concerne QUE l'événement.
                # (On pourra toujours retrouver le club via obj.event.club si besoin pour l'affichage)
                obj.club = None
                
            elif obj.club:
                # CAS 2 : Pas d'event, mais un Club est sélectionné
                # La candidature concerne le Club directement.
                pass # On garde obj.club tel quel

            # --------------------------------------------------

            if not annonce:
                obj.publisher = request.user
                obj.publisher_type = 'admin'
            
            obj.save()
            form.save_m2m()
            
            if id:
                messages.success(request, "Annonce modifiée avec succès !")
            else:
                messages.success(request, "Annonce créée avec succès !")
            return redirect('admin_dashboard') 
    else:
        form = AnnonceForm(instance=annonce)

    return render(request, 'recrutement/create_annonce.html', {
        'form': form, 
        'titre_page': titre_page
    })


# ==========================================
# 3. POSTULER (MODIFIÉ AVEC RÈGLES STRICTES)
# ==========================================
def postuler(request, annonce_id):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('signin')}?next={request.path}")

    annonce = get_object_or_404(Annonce, pk=annonce_id)
    
    # On identifie les contextes (Club ou Event)
    club_concerne = annonce.club if hasattr(annonce, 'club') else None
    event_concerne = annonce.event if hasattr(annonce, 'event') else None

    # On récupère l'historique des candidatures de cet utilisateur pour CETTE annonce
    historique = Candidature.objects.filter(username=request.user.username, annonce=annonce)

    # ==============================================================================
    # 1. LOGIQUE DE BLOCAGE INTELLIGENT (PROMOTION INTERNE)
    # ==============================================================================

    # A. Si l'utilisateur a déjà été REFUSÉ -> BANNI de cette annonce
    if historique.filter(status='refusee').exists():
        messages.error(request, "Votre candidature précédente a été refusée. Vous ne pouvez plus postuler à cette annonce.")
        return redirect('home')

    # B. Si l'utilisateur a une candidature EN ATTENTE -> DOIT ATTENDRE
    if historique.filter(status='en_attente').exists():
        messages.warning(request, "Vous avez déjà une candidature en cours de traitement. Veuillez attendre la réponse.")
        return redirect('home')

    # C. Si l'utilisateur est déjà accepté comme CHEF ou PRÉSIDENT -> STOP (Grade Max atteint)
    if historique.filter(status='acceptee', profil_souhaite__in=['chef_cellule', 'president']).exists():
        messages.info(request, "Vous avez déjà obtenu un poste à responsabilité via cette annonce.")
        return redirect('home')

    # D. Cas Spécial : Si déjà accepté comme MEMBRE
    deja_membre_accepte = historique.filter(status='acceptee', profil_souhaite='membre').exists()

    # ==============================================================================

    if request.method == 'POST':
        form = CandidatureForm(request.POST, annonce=annonce, user=request.user)

        if form.is_valid():
            profil_choisi = form.cleaned_data.get('profil_souhaite')
            cellule_choisie = form.cleaned_data.get('cellule') # On récupère la cellule choisie

            # ==================================================================
            # NOUVELLE RÈGLE : MEMBRE = CELLULE OBLIGATOIRE
            # ==================================================================
            if profil_choisi == 'membre' and not cellule_choisie:
                messages.error(request, "Erreur : Pour postuler en tant que Membre, vous devez OBLIGATOIREMENT choisir une cellule.")
                # On réaffiche le formulaire avec l'erreur sans sauvegarder
                return render(request, 'recrutement/postuler.html', {'form': form, 'annonce': annonce})
            # ==================================================================
            
            # --- VERIFICATION PROMOTION INTERNE ---
            if deja_membre_accepte and profil_choisi == 'membre':
                messages.error(request, "Vous êtes déjà Membre accepté. Pour repostuler, vous devez viser un poste supérieur (Chef de cellule ou Président).")
                return render(request, 'recrutement/postuler.html', {'form': form, 'annonce': annonce})

            # --- RÈGLES DE HIERARCHIE ---
            # Vérifications CLUB
            if club_concerne:
                if profil_choisi == 'chef_cellule' and club_concerne.president == request.user:
                    messages.error(request, "Interdit : Le Président du club ne peut pas être Chef de cellule.")
                    return redirect('home')
                if profil_choisi == 'president' and Cellule.objects.filter(club=club_concerne, chef=request.user).exists():
                    messages.error(request, "Interdit : Un Chef de cellule ne peut pas devenir Président sans démissionner.")
                    return redirect('home')
                
                est_membre = club_concerne.membres.filter(pk=request.user.pk).exists()
                if not est_membre and profil_choisi in ['chef_cellule', 'president']:
                    messages.error(request, "Refusé : Vous devez d'abord être Membre pour prétendre à ce poste.")
                    return redirect('home')

            # Vérifications EVENT
            if event_concerne:
                if profil_choisi == 'chef_cellule' and event_concerne.president == request.user:
                    messages.error(request, "Interdit : Le Président de l'événement ne peut pas postuler comme Chef de cellule.")
                    return redirect('home')
                if profil_choisi == 'president' and Cellule.objects.filter(event=event_concerne, chef=request.user).exists():
                    messages.error(request, "Interdit : Un Chef de cellule ne peut pas devenir Président de l'événement.")
                    return redirect('home')

            # Sauvegarde
            candidature = form.save(commit=False)
            candidature.annonce = annonce 
            if club_concerne: candidature.club = club_concerne
            if event_concerne: candidature.event = event_concerne
            
            candidature.prenom = request.user.first_name
            candidature.nom = request.user.last_name
            candidature.email = request.user.email
            candidature.username = request.user.username
            
            candidature.save()
            
            if deja_membre_accepte:
                messages.success(request, "Votre candidature pour un poste supérieur a été envoyée !")
            else:
                messages.success(request, "Votre candidature a été envoyée avec succès !")
                
            return redirect('home')
        else:
             messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")
    else:
        form = CandidatureForm(annonce=annonce, user=request.user)

    return render(request, 'recrutement/postuler.html', {
        'form': form,
        'annonce': annonce
    })

# ==========================================
# 4. ADMIN CANDIDATURES (Inchangé)
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
# 5. TRAITER CANDIDATURE (MODIFIÉ AVEC SÉCURITÉ FINALE)
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

    if action == 'accepter':
        user, created = User.objects.get_or_create(
            username=cand.username,
            defaults={'email': cand.email, 'first_name': cand.prenom, 'last_name': cand.nom}
        )
        if not created:
             user = User.objects.get(username=cand.username)

        # --- SÉCURITÉ FINALE : Vérification des conflits avant validation ---
        
        # CAS CLUB
        if cand.club:
            if cand.profil_souhaite == 'chef_cellule' and cand.club.president == user:
                messages.error(request, "Impossible : Cet utilisateur est déjà le PRÉSIDENT de ce club.")
                cand.status = 'refusee'
                cand.save()
                return redirect('admin_candidatures', annonce_id=cand.annonce.id)

            if cand.profil_souhaite == 'president' and Cellule.objects.filter(club=cand.club, chef=user).exists():
                messages.error(request, "Impossible : Cet utilisateur est déjà CHEF de cellule dans ce club.")
                cand.status = 'refusee'
                cand.save()
                return redirect('admin_candidatures', annonce_id=cand.annonce.id)

        # CAS EVENT
        if cand.event:
            if cand.profil_souhaite == 'chef_cellule' and cand.event.president == user:
                messages.error(request, "Impossible : Cet utilisateur est déjà le PRÉSIDENT de cet événement.")
                cand.status = 'refusee'
                cand.save()
                return redirect('admin_candidatures', annonce_id=cand.annonce.id)

            if cand.profil_souhaite == 'president' and Cellule.objects.filter(event=cand.event, chef=user).exists():
                messages.error(request, "Impossible : Cet utilisateur est déjà CHEF de cellule dans cet événement.")
                cand.status = 'refusee'
                cand.save()
                return redirect('admin_candidatures', annonce_id=cand.annonce.id)


        # --- VÉRIFICATIONS STANDARDS (Poste déjà occupé par QUELQU'UN D'AUTRE) ---
        if cand.profil_souhaite == 'president':
            if cand.club and cand.club.president and cand.club.president != user:
                cand.status = 'refusee'
                cand.save()
                messages.error(request, f"Le club {cand.club.nom} a déjà un autre président.")
                return redirect('admin_candidatures', annonce_id=cand.annonce.id)
            if cand.event and cand.event.president and cand.event.president != user:
                cand.status = 'refusee'
                cand.save()
                messages.error(request, "Cet évènement a déjà un autre président.")
                return redirect('admin_candidatures', annonce_id=cand.annonce.id)

        if cand.profil_souhaite == 'chef_cellule':
            if cand.cellule and cand.cellule.chef and cand.cellule.chef != user:
                cand.status = 'refusee'
                cand.save()
                messages.error(request, f"La cellule {cand.cellule.nom} a déjà un chef.")
                return redirect('admin_candidatures', annonce_id=cand.annonce.id)


        # --- TOUT EST OK : ON APPLIQUE LES CHANGEMENTS ---
        
        # Mise à jour User
        user.email = cand.email
        user.first_name = cand.prenom
        user.last_name = cand.nom
        if created:
            if cand.password: user.set_password(cand.password)
            else: user.set_password('Defaut1234!') 
        user.save()

        # Affectation des rôles
        if cand.profil_souhaite == 'president':
            if cand.club:
                cand.club.president = user
                cand.club.save()
            elif cand.event:
                cand.event.president = user
                cand.event.save()

        elif cand.profil_souhaite == 'chef_cellule' and cand.cellule:
            cand.cellule.chef = user
            cand.cellule.save()
            if cand.cellule.event:
                 cand.cellule.event.chefs.add(user)

        else: # Cas Membre
            if cand.club: cand.club.membres.add(user)
            if cand.cellule: cand.cellule.membres.add(user)

        # Profil & Mail
        Profil.objects.update_or_create(user=user, defaults={'profil': cand.profil_souhaite})
        
        send_mail(
            'Candidature acceptée',
            f"Bonjour {cand.prenom},\nFélicitations ! Votre candidature pour le poste de {cand.profil_souhaite.replace('_',' ')} a été acceptée !",
            'admin@club.com', [cand.email], fail_silently=True
        )
        cand.status = 'acceptee'

    else:
        # Refuser
        cand.status = 'refusee'
        send_mail(
            'Candidature refusée',
            f"Bonjour {cand.prenom}, votre candidature pour {cand.profil_souhaite} a été refusée.",
            'admin@club.com', [cand.email], fail_silently=True
        )

    cand.processed_at = timezone.now()
    cand.processed_by = request.user
    cand.save()

    return redirect('admin_candidatures', annonce_id=cand.annonce.id)

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