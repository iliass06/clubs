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
    cellules = Cellule.objects.none()
    
    if club_id:
        cellules = cellules | Cellule.objects.filter(club_id=club_id)
        events_qs = Event.objects.filter(club_id=club_id).values('id', 'titre')
        return JsonResponse({
            'cellules': list(cellules.distinct().values('id', 'nom')),
            'events': list(events_qs)
        })
    
    if event_id:
        cellules = cellules | Cellule.objects.filter(event_id=event_id)

    cellules_list = list(cellules.distinct().values('id', 'nom'))
    return JsonResponse({'cellules': cellules_list})


# ==========================================
# 2. GESTION ANNONCE (Inchangé)
# ==========================================
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
    club_concerne = annonce.club if hasattr(annonce, 'club') else None
    event_concerne = annonce.event if hasattr(annonce, 'event') else None

    # Vérification si candidature déjà en cours
    if Candidature.objects.filter(username=request.user.username, annonce=annonce).exclude(status__in=['acceptee', 'refusee']).exists():
            messages.warning(request, "Vous avez déjà une candidature en cours pour cette annonce.")
            return redirect('home')

    if request.method == 'POST':
        form = CandidatureForm(request.POST, annonce=annonce, user=request.user)

        if form.is_valid():
            profil_choisi = form.cleaned_data.get('profil_souhaite')
            
            # --- RÈGLE D'OR : PAS DE DOUBLE CASQUETTE (Président <-> Chef) ---
            
            # 1. Vérification pour CLUB
            if club_concerne:
                # Si je veux être CHEF alors que je suis PRÉSIDENT
                if profil_choisi == 'chef_cellule' and club_concerne.president == request.user:
                    messages.error(request, "Interdit : Le Président du club ne peut pas être Chef de cellule dans le même club.")
                    return redirect('home')

                # Si je veux être PRÉSIDENT alors que je suis CHEF
                if profil_choisi == 'president' and Cellule.objects.filter(club=club_concerne, chef=request.user).exists():
                    messages.error(request, "Interdit : Un Chef de cellule ne peut pas devenir Président du même club sans démissionner d'abord.")
                    return redirect('home')

                # Promotion interne
                est_membre = club_concerne.membres.filter(pk=request.user.pk).exists()
                if not est_membre and profil_choisi in ['chef_cellule', 'president']:
                    messages.error(request, "Refusé : Vous devez d'abord être Membre pour prétendre à ce poste.")
                    return redirect('home')

            # 2. Vérification pour EVENT
            if event_concerne:
                # Si je veux être CHEF alors que je suis PRÉSIDENT EVENT
                if profil_choisi == 'chef_cellule' and event_concerne.president == request.user:
                    messages.error(request, "Interdit : Le Président de l'événement ne peut pas être Chef de cellule dans le même événement.")
                    return redirect('home')

                # Si je veux être PRÉSIDENT EVENT alors que je suis CHEF
                if profil_choisi == 'president' and Cellule.objects.filter(event=event_concerne, chef=request.user).exists():
                    messages.error(request, "Interdit : Un Chef de cellule ne peut pas devenir Président du même événement.")
                    return redirect('home')

            candidature = form.save(commit=False)
            candidature.annonce = annonce 
            if club_concerne: candidature.club = club_concerne
            if event_concerne: candidature.event = event_concerne
            
            candidature.prenom = request.user.first_name
            candidature.nom = request.user.last_name
            candidature.email = request.user.email
            candidature.username = request.user.username
            
            candidature.save()
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