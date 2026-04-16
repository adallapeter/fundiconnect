# users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.forms import formset_factory
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.db.models import Q, Avg, Count, F
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET, require_POST
from django_otp import login as otp_login
from django.utils import timezone
import json

from .assistant import assistant_reply, persist_assistant_exchange
from .models import CustomUser, ArtisanProfile, PortfolioImage, Certification, ClientProfile, Notification, MessageAttachment
from .forms import CustomUserCreationForm, ArtisanProfileForm, PortfolioImageForm, CertificationForm, ClientProfileForm
from jobs.models import Job, Bid, Reviews, Category  # Assuming these models exist

# Add these imports at the top
import requests
import json
from django.conf import settings

# Email Verification Views
@login_required
def verify_email(request):
    if request.user.email_verified:
        return redirect('home')

    if not request.user.email_verification_code and not request.user.is_email_verification_locked():
        request.user.send_verification_email()

    if request.user.is_email_verification_locked():
        locked_until = request.user.email_verification_locked_until
        message = f'Too many incorrect attempts. Try again after {timezone.localtime(locked_until).strftime("%b %d, %Y %I:%M %p")}.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'locked': True, 'message': message})
        messages.error(request, message)
        return render(request, 'users/verify_email.html', {'locked_until': locked_until})
    
    if request.method == 'POST':
        # Check if the token matches
        token = ''.join(ch for ch in (request.POST.get('token') or '') if ch.isdigit())
        if token and len(token) == 6 and request.user.email_verification_code and token == request.user.email_verification_code:
            request.user.email_verified = True
            request.user.email_verification_attempts = 0
            request.user.email_verification_locked_until = None
            request.user.save(update_fields=['email_verified', 'email_verification_attempts', 'email_verification_locked_until'])
            messages.success(request, 'Email verified successfully!')
            
            # Send phone verification code if phone number exists
            redirect_url = 'users:verify_phone' if request.user.needs_phone_verification() else 'users:complete_profile'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': True, 'redirect_url': redirect(redirect_url).url})
            return redirect(redirect_url)
        else:
            locked_until = request.user.register_failed_email_attempt()
            if locked_until and request.user.is_email_verification_locked():
                message = f'Too many incorrect attempts. Try again after {timezone.localtime(locked_until).strftime("%b %d, %Y %I:%M %p")}.'
            else:
                message = 'Invalid verification code.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'locked': bool(locked_until and request.user.is_email_verification_locked()), 'message': message})
            messages.error(request, message)
    
    return render(request, 'users/verify_email.html')

# views.py
@login_required
def resend_verification_email(request):
    if request.user.email_verified:
        messages.info(request, 'Your email is already verified.')
        return redirect('users:dashboard')

    if request.user.is_email_verification_locked():
        locked_until = request.user.email_verification_locked_until
        message = f'Too many incorrect attempts. Try again after {timezone.localtime(locked_until).strftime("%b %d, %Y %I:%M %p")}.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'message': message})
        messages.error(request, message)
        return redirect('users:verify_email')
    
    if request.method == 'POST':
        # Send verification email
        if request.user.send_verification_email():
            messages.success(request, 'Verification email sent! Check your inbox for the 6-digit code.')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': True, 'message': 'Verification email sent. Check your inbox.'})
        else:
            messages.error(request, 'Failed to send verification email. Please try again later.')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'message': 'Failed to send verification email. Please try again later.'})
        return redirect('users:verify_email')
    
    return render(request, 'users/resend_verification_email.html')


@require_POST
def assistant_respond(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        payload = {}

    prompt = (payload.get('prompt') or payload.get('content') or '').strip()
    if not prompt:
        return JsonResponse({'ok': False, 'error': 'Prompt is required.'}, status=400)

    user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None
    context = payload.get('context', None)
    path = payload.get('path') or request.path
    response = assistant_reply(prompt, user=user, context=context, path=path)
    persist_assistant_exchange(user, prompt, response)
    return JsonResponse({'ok': True, 'data': response})


@require_GET
def location_search(request):
    query = (request.GET.get('q') or '').strip()
    if len(query) < 3:
        return JsonResponse({'results': []})
    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'format': 'jsonv2',
                'limit': 6,
                'q': query,
            },
            headers={
                'User-Agent': 'FundiConnect/1.0 location-search',
                'Accept-Language': 'en',
            },
            timeout=20,
        )
        response.raise_for_status()
        return JsonResponse({'results': response.json()})
    except requests.RequestException:
        return JsonResponse({'results': [], 'error': 'Location lookup is temporarily unavailable.'}, status=200)


@require_GET
def location_reverse(request):
    lat = (request.GET.get('lat') or '').strip()
    lon = (request.GET.get('lon') or '').strip()
    if not lat or not lon:
        return JsonResponse({'error': 'Latitude and longitude are required.'}, status=400)
    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={
                'format': 'jsonv2',
                'lat': lat,
                'lon': lon,
            },
            headers={
                'User-Agent': 'FundiConnect/1.0 location-reverse',
                'Accept-Language': 'en',
            },
            timeout=20,
        )
        response.raise_for_status()
        return JsonResponse(response.json())
    except requests.RequestException:
        return JsonResponse({'error': 'Reverse geocoding is temporarily unavailable.'}, status=200)
# Phone Verification Views
@login_required
def verify_phone(request):
    if not request.user.email_verified:
        return redirect('users:verify_email')
    
    if request.user.phone_verified or request.user.phone_verification_skipped:
        return redirect('users:complete_profile')
    
    if request.method == 'POST':
        code = request.POST.get('code')
        if request.user.verify_phone_code(code):
            messages.success(request, 'Phone number verified successfully!')
            return redirect('users:complete_profile')
        else:
            messages.error(request, 'Invalid or expired verification code.')
    
    return render(request, 'users/verify_phone.html', {
        'phone_number': request.user.phone_number
    })

@login_required
@require_POST
def skip_phone_verification(request):
    if request.user.phone_verified:
        return redirect('users:complete_profile')
    request.user.phone_verification_skipped = True
    request.user.save(update_fields=['phone_verification_skipped'])
    messages.info(request, 'Phone verification skipped. You can verify it later in settings.')
    return redirect('users:complete_profile')

@login_required
def send_phone_verification(request):
    if not request.user.email_verified:
        return redirect('users:verify_email')
    
    if request.user.phone_verified:
        return redirect('users:complete_profile')

    if not request.user.phone_number:
        messages.error(request, 'Please add a phone number before requesting verification.')
        return redirect('users:verify_phone')

    request.user.phone_verification_skipped = False
    request.user.save(update_fields=['phone_verification_skipped'])
    
    # Generate verification code
    code = request.user.generate_phone_verification_code()
    
    # Send SMS using Safaricom Daraja API
    # Note: This is a simplified example. You'll need to implement proper authentication
    # and error handling based on the Daraja API documentation
    
    # Prepare the message
    message = f"Your FundiConnect verification code is: {code}. It expires in 10 minutes."
    
    # Daraja API credentials (you should store these in settings/environment variables)
    consumer_key = settings.DARAJA_CONSUMER_KEY
    consumer_secret = settings.DARAJA_CONSUMER_SECRET
    shortcode = settings.DARAJA_SHORTCODE
    
    # Get access token
    auth_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    auth_response = requests.get(auth_url, auth=(consumer_key, consumer_secret))
    
    if auth_response.status_code == 200:
        access_token = auth_response.json().get('access_token')
        
        # Send SMS
        sms_url = 'https://sandbox.safaricom.co.ke/mpesa/sms/v1/send'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "sender": shortcode,
            "message": message,
            "to": request.user.phone_number  # Assuming phone is in format 2547XXXXXXXX
        }
        
        response = requests.post(sms_url, headers=headers, data=json.dumps(payload))
        
        if response.status_code == 200:
            messages.success(request, 'Verification code sent to your phone!')
        else:
            messages.error(request, 'Failed to send verification code. Please try again.')
    else:
        messages.error(request, 'Failed to authenticate with SMS service.')
    
    return redirect('users:verify_phone')

@login_required
def complete_profile(request):
    # Check if email and phone are verified first
    if not request.user.email_verified:
        return redirect('users:verify_email')
    elif request.user.needs_phone_verification():
        return redirect('users:verify_phone')
    
    if request.user.profile_completed:
        return redirect('users:dashboard')
    
    
    if request.user.is_client:
        try:
            profile = request.user.client_profile
        except ClientProfile.DoesNotExist:
            # Create a new client profile if it doesn't exist
            profile = ClientProfile.objects.create(user=request.user)
        
        if request.method == 'POST':
            form = ClientProfileForm(request.POST, instance=profile)
            if form.is_valid():
                form.save()
                request.user.profile_completed = True
                request.user.save()
                messages.success(request, 'Profile completed successfully!')
                return redirect('users:dashboard')
            else:
                # Add form errors to messages
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        else:
            form = ClientProfileForm(instance=profile)
        
        return render(request, 'users/complete_client_profile.html', {
            'form': form,
        })
    
    elif request.user.is_artisan:
        # For artisans, redirect to artisan profile completion
        try:
            artisan_profile = request.user.artisan_profile
            # If profile exists but isn't complete, redirect to edit
            if not artisan_profile.full_name:  # Check if profile is actually complete
                return redirect('users:complete_artisan_profile')
            else:
                # Profile is complete, mark it as such
                request.user.profile_completed = True
                request.user.save()
                return redirect('users:dashboard')
        except ArtisanProfile.DoesNotExist:
            return redirect('users:complete_artisan_profile')
    
    else:
        messages.error(request, "Invalid user type.")
        return redirect('home')
def register(request):
    if request.user.is_authenticated:
        if not request.user.email_verified:
            return redirect('users:verify_email')
        if request.user.needs_phone_verification():
            return redirect('users:verify_phone')
        if not request.user.profile_completed:
            return redirect('users:complete_profile')
        return redirect('users:dashboard')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email_verified = False
            user.phone_verified = False
            user.profile_completed = False
            user.save()
            
            # Create appropriate profile based on user type
            if user.is_client:
                ClientProfile.objects.create(user=user)
            elif user.is_artisan:
                ArtisanProfile.objects.create(user=user)
            
            # Send verification email
            user.send_verification_email()
            
            # Log the user in
            login(request, user)
            
            messages.success(request, 'Account created successfully! Please check your email for verification instructions.')
            
            # Redirect to email verification, not profile completion
            return redirect('users:verify_email')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'users/register.html', {'form': form})

@login_required
def complete_artisan_profile(request):
    # Check if user is an artisan
    if not request.user.is_artisan:
        messages.error(request, "This page is only for artisans.")
        return redirect('home')
    
    # Check if email and phone are verified first
    if not request.user.email_verified:
        return redirect('users:verify_email')
    elif request.user.needs_phone_verification():
        return redirect('users:verify_phone')
    
    if request.user.profile_completed:
        return redirect('users:dashboard')
        
    # Check if profile already exists
    try:
        artisan_profile = request.user.artisan_profile
    except ArtisanProfile.DoesNotExist:
        artisan_profile = None
    
    PortfolioImageFormSet = formset_factory(PortfolioImageForm, extra=3, max_num=10)
    CertificationFormSet = formset_factory(CertificationForm, extra=1, max_num=5)
    
    if request.method == 'POST':
        profile_form = ArtisanProfileForm(request.POST, request.FILES, instance=artisan_profile)
        portfolio_formset = PortfolioImageFormSet(request.POST, request.FILES, prefix='portfolio')
        certification_formset = CertificationFormSet(request.POST, prefix='certification')
        
        if profile_form.is_valid() and portfolio_formset.is_valid() and certification_formset.is_valid():
            # Save artisan profile
            artisan_profile = profile_form.save(commit=False)
            artisan_profile.user = request.user
            artisan_profile.save()
            
            # Save portfolio images
            for form in portfolio_formset:
                if form.cleaned_data.get('image'):
                    portfolio_image = form.save(commit=False)
                    portfolio_image.artisan = artisan_profile
                    portfolio_image.save()
            
            # Save certifications
            for form in certification_formset:
                if form.cleaned_data.get('name'):
                    certification = form.save(commit=False)
                    certification.save()
                    artisan_profile.certifications.add(certification)
            
            # Mark user as having completed profile
            request.user.profile_completed = True
            request.user.save()
            
            messages.success(request, "Your professional profile has been created successfully!")
            return redirect('users:dashboard')
    else:
        profile_form = ArtisanProfileForm(instance=artisan_profile)
        portfolio_formset = PortfolioImageFormSet(prefix='portfolio')
        certification_formset = CertificationFormSet(prefix='certification')
    
    context = {
        'profile_form': profile_form,
        'portfolio_formset': portfolio_formset,
        'certification_formset': certification_formset,
    }
    
    return render(request, 'users/complete_artisan_profile.html', context)

@login_required
def edit_artisan_profile(request):
    # Check if user is an artisan
    if not request.user.is_artisan:
        messages.error(request, "This page is only for artisans.")
        return redirect('home')
    
    # Get artisan profile or return 404
    artisan_profile = get_object_or_404(ArtisanProfile, user=request.user)
    
    PortfolioImageFormSet = formset_factory(PortfolioImageForm, extra=3, max_num=10)
    CertificationFormSet = formset_factory(CertificationForm, extra=1, max_num=5)
    
    if request.method == 'POST':
        profile_form = ArtisanProfileForm(request.POST, request.FILES, instance=artisan_profile)
        portfolio_formset = PortfolioImageFormSet(request.POST, request.FILES, prefix='portfolio')
        certification_formset = CertificationFormSet(request.POST, prefix='certification')
        
        if profile_form.is_valid() and portfolio_formset.is_valid() and certification_formset.is_valid():
            # Save artisan profile
            profile_form.save()
            
            # Save portfolio images
            for form in portfolio_formset:
                if form.cleaned_data.get('image'):
                    portfolio_image = form.save(commit=False)
                    portfolio_image.artisan = artisan_profile
                    portfolio_image.save()
            
            # Save certifications
            for form in certification_formset:
                if form.cleaned_data.get('name'):
                    certification = form.save(commit=False)
                    certification.save()
                    artisan_profile.certifications.add(certification)
            
            messages.success(request, "Your professional profile has been updated successfully!")
            return redirect('users:dashboard')
    else:
        profile_form = ArtisanProfileForm(instance=artisan_profile)
        portfolio_formset = PortfolioImageFormSet(prefix='portfolio')
        certification_formset = CertificationFormSet(prefix='certification')
    
    context = {
        'profile_form': profile_form,
        'portfolio_formset': portfolio_formset,
        'certification_formset': certification_formset,
        'artisan_profile': artisan_profile,
    }
    
    return render(request, 'users/edit_artisan_profile.html', context)


def login_view(request):
    """
    Handles user login with 2FA support.
    """
    if request.user.is_authenticated:
        if not request.user.email_verified:
            return redirect('users:verify_email')
        if user_has_device(request.user) and not request.user.is_verified():
            return redirect('users:two_factor_verify')
        if request.user.needs_phone_verification():
            return redirect('users:verify_phone')
        if not request.user.profile_completed:
            return redirect('users:complete_profile')
        return redirect('users:dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                # Check if user has 2FA enabled
                if user.two_factor_enabled:
                    # Store user ID in session for 2FA verification
                    request.session['user_id_for_2fa'] = user.id
                    return redirect('users:two_factor_verify')
                else:
                    login(request, user)
                    
                    # Check what step the user needs to complete
                    if not user.email_verified:
                        return redirect('users:verify_email')
                    elif user.needs_phone_verification():
                        return redirect('users:verify_phone')
                    elif not user.profile_completed:
                        return redirect('users:complete_profile')
                    else:
                        messages.info(request, f"You are now logged in as {username}.")
                        return redirect('users:dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    
    context = {'form': form}
    return render(request, 'users/login.html', context)
    
@login_required
def logout_view(request):
    """
    Logs the user out and redirects them to the home page.
    """
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('home')

@login_required
def dashboard(request):
    user = request.user
    context = {'user': user}
    
    if user.is_client:
        client_jobs = Job.objects.filter(client=user).select_related('category').order_by('-updated_at')
        active_projects = client_jobs.filter(status__in=['open', 'in_progress'])[:5]
        pending_bids = Bid.objects.filter(job__client=user, status='pending').select_related('artisan__user', 'job')
        client_reviews = Reviews.objects.filter(recipient=user)
        unread_messages = Message.objects.filter(
            conversation__participants=user,
            is_read=False,
        ).exclude(sender=user).count()

        satisfaction_rate = 0
        if client_reviews.exists():
            satisfaction_rate = round((client_reviews.filter(rating__gte=4).count() / client_reviews.count()) * 100)
        
        stats = {
            'active_projects': client_jobs.filter(status='in_progress').count(),
            'pending_bids': pending_bids.count(),
            'bids_needing_review': pending_bids.count(),
            'completed_jobs': client_jobs.filter(status='completed').count(),
            'satisfaction_rate': satisfaction_rate,
            'unread_messages': unread_messages,
            'messages_from_artisans': unread_messages,
        }
        
        recommended_artisans = ArtisanProfile.objects.filter(availability='available').order_by('-rating', '-completed_projects')[:3]
        recent_activity = []
        for job in client_jobs[:4]:
            recent_activity.append({
                'type': 'job_update',
                'description': f'"{job.title}" is now {job.get_status_display().lower()}',
                'timestamp': job.updated_at,
                'type_color': 'completed' if job.status == 'completed' else 'new' if job.status == 'in_progress' else 'pending'
            })
        
        for bid in pending_bids[:3]:
            recent_activity.append({
                'type': 'bid_received',
                'description': f'{bid.artisan.user.display_name} bid on "{bid.job.title}"',
                'timestamp': bid.created_at,
                'type_color': 'new'
            })
        
        recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
        budget_data = {
            'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            'data': [0, 1, 2, 3, 2, client_jobs.filter(status='completed').count()],
        }
        
        context.update({
            'stats': stats,
            'active_projects': active_projects,
            'recommended_artisans': recommended_artisans,
            'recent_activity': recent_activity[:5],
            'budget_data': budget_data,
        })
        return render(request, 'users/client_dashboard.html', context)
    
    elif user.is_artisan:
        try:
            artisan_profile = user.artisan_profile
        except ArtisanProfile.DoesNotExist:
            messages.warning(request, "Please complete your artisan profile to access all features.")
            return redirect('users:complete_artisan_profile')
        
        active_jobs = Job.objects.filter(
            status='in_progress',
            bids__artisan=artisan_profile,
            bids__status='accepted'
        ).distinct().order_by('-updated_at')
        artisan_bids = Bid.objects.filter(artisan=artisan_profile).select_related('job', 'job__category').order_by('-updated_at')
        completed_jobs = Job.objects.filter(
            status='completed', 
            bids__artisan=artisan_profile,
            bids__status='accepted'
        ).distinct().count()
        unread_messages = Message.objects.filter(
            conversation__participants=user,
            is_read=False,
        ).exclude(sender=user).count()

        stats = {
            'active_jobs': active_jobs.count(),
            'pending_bids': artisan_bids.filter(status='pending').count(),
            'completed_jobs': completed_jobs,
            'unread_messages': unread_messages,
        }
        
        recent_jobs = Job.objects.filter(
            status='open'
        ).exclude(
            bids__artisan=artisan_profile
        ).order_by('-created_at')
        if artisan_profile.category:
            recent_jobs = recent_jobs.filter(
                Q(category__slug__iexact=artisan_profile.category) |
                Q(category__name__iexact=artisan_profile.get_category_display())
            )
        recent_jobs = recent_jobs[:5]
        
        recent_activity = []
        for bid in artisan_bids[:4]:
            recent_activity.append({
                'type': 'bid_placed',
                'description': f'Your bid for "{bid.job.title}" is {bid.get_status_display().lower()}',
                'timestamp': bid.updated_at,
                'type_color': 'new' if bid.status == 'pending' else 'completed' if bid.status == 'accepted' else 'warning'
            })
        
        for job in active_jobs[:3]:
            recent_activity.append({
                'type': 'job_update',
                'description': f'"{job.title}" is currently {job.get_status_display().lower()}',
                'timestamp': job.updated_at,
                'type_color': 'new'
            })
        
        recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
        
        context.update({
            'artisan_profile': artisan_profile,
            'stats': stats,
            'recent_jobs': recent_jobs,
            'recent_activity': recent_activity[:5],
            'active_jobs': active_jobs[:5],
        })
        return render(request, 'users/artisan_dashboard.html', context)
    
    else:
        # Fallback for users without a specific type
        messages.warning(request, "Your user type is not recognized. Please contact support.")
        return redirect('home')
        
@login_required
def artisans(request):
    artisans = ArtisanProfile.objects.filter(user__user_type='artisan').order_by('-created_at')
    categories = Category.objects.all().order_by('name')
    context = {
        'artisans': artisans,
        'categories': categories,
    }
    return render(request, 'users/artisans.html', context)

@login_required
def artisan_detail(request, artisan_id):
    artisan = get_object_or_404(ArtisanProfile, id=artisan_id)
    if not request.user.is_authenticated or request.user != artisan.user:
        ArtisanProfile.objects.filter(id=artisan.id).update(profile_views=F('profile_views') + 1)
        artisan.profile_views += 1
    context = {'artisan': artisan}
    return render(request, 'users/artisan_detail.html', context)


@login_required
@require_GET
def artisan_reviews_ajax(request, artisan_user_id):
    """Return rendered reviews for an artisan as HTML (JSON payload) for AJAX modals."""
    try:
        reviews_qs = Reviews.objects.filter(recipient__id=artisan_user_id, review_type='client_to_artisan').select_related('author')
    except Exception:
        return JsonResponse({'ok': False, 'html': '', 'count': 0})

    total = reviews_qs.count()
    avg = reviews_qs.aggregate(avg=Avg('rating'))['avg'] or 0
    positive_count = reviews_qs.filter(rating__gte=4).count()
    positive_ratio = (positive_count / total) if total else 0

    # Satisfaction metric: weighted blend of average rating and positive review ratio
    satisfaction_rate = int(round((avg / 5.0) * 0.6 * 100 + positive_ratio * 0.4 * 100)) if total else 0

    reviews_html = render_to_string('partials/reviews_list.html', {'reviews': reviews_qs[:20]}, request=request)
    modal_html = render_to_string('partials/artisan_reviews_modal.html', {'reviews_html': reviews_html}, request=request)

    return JsonResponse({'ok': True, 'html': modal_html, 'satisfaction_rate': satisfaction_rate, 'count': total})

@login_required
def artisan_list_ajax(request):
    artisans = ArtisanProfile.objects.filter(availability='available').order_by('-rating', '-completed_projects')

    availability = request.GET.get('availability')
    if availability:
        artisans = artisans.filter(availability=availability)

    category_slug = request.GET.get('category')
    if category_slug:
        artisans = artisans.filter(Q(category__iexact=category_slug) | Q(category__icontains=category_slug))

    location_filter = request.GET.get('location')
    if location_filter:
        artisans = artisans.filter(location__icontains=location_filter)

    skill_filter = request.GET.get('skill')
    if skill_filter:
        artisans = artisans.filter(
            Q(specialization__icontains=skill_filter)
            | Q(description__icontains=skill_filter)
        )
    
    rate_filter = request.GET.get('rate')
    if rate_filter == 'low':
        artisans = artisans.filter(hourly_rate__lt=500)
    elif rate_filter == 'medium':
        artisans = artisans.filter(hourly_rate__gte=500, hourly_rate__lte=1500)
    elif rate_filter == 'high':
        artisans = artisans.filter(hourly_rate__gt=1500)
    
    rating_filter = request.GET.get('rating')
    if rating_filter:
        min_rating = float(rating_filter)
        artisans = artisans.filter(rating__gte=min_rating)

    search_query = request.GET.get('q')
    if search_query:
        artisans = artisans.filter(
            Q(full_name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(specialization__icontains=search_query) |
            Q(location__icontains=search_query)
        ).distinct()
    
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'rating':
        artisans = artisans.order_by('-rating', '-completed_projects')
    elif sort_by == 'rate_high':
        artisans = artisans.order_by('-hourly_rate')
    elif sort_by == 'rate_low':
        artisans = artisans.order_by('hourly_rate')
    else:
        artisans = artisans.order_by('-created_at')
    
    paginator = Paginator(artisans, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    html = render_to_string('partials/artisans_list.html', {
        'artisans': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
        'request': request
    })
    
    description = "Skilled professionals ready for your projects"
    if search_query:
        description = f'Search results for "{search_query}"'
    elif category_slug:
        category = Category.objects.filter(slug=category_slug).first()
        if category:
            description = f"Showing {category.name} specialists"
    
    return JsonResponse({
        'html': html,
        'count': page_obj.paginator.count,
        'count_text': f'{page_obj.paginator.count} Fundi{"s" if page_obj.paginator.count != 1 else ""} Available',
        'description': description,
        'total_count': ArtisanProfile.objects.filter(availability='available').count()
    })

@login_required
def profile(request):
    user = request.user
    context = {
        'user': user,
        'is_artisan': user.is_artisan,
    }
    return render(request, 'users/profile.html', context)

@login_required
def upload_portfolio_image(request):
    if request.user.is_authenticated and request.FILES.get('file'):
        profile = ArtisanProfile.objects.get(user=request.user)
        image = PortfolioImage.objects.create(artisan=profile, image=request.FILES['file'])
        return JsonResponse({'status': 'success', 'image_url': image.image.url})
    return JsonResponse({'status': 'error', 'message': 'Upload failed'}, status=400)

@login_required
def delete_portfolio_image(request, pk):
    image = get_object_or_404(PortfolioImage, pk=pk, artisan__user=request.user)
    image.delete()
    messages.success(request, "Portfolio image deleted successfully.")
    return redirect('users:edit_artisan_profile')

@login_required
def delete_certification(request, pk):
    certification = get_object_or_404(Certification, pk=pk)
    # Remove from artisan profile but don't delete the certification object entirely
    request.user.artisan_profile.certifications.remove(certification)
    messages.success(request, "Certification removed from your profile.")
    return redirect('users:edit_artisan_profile')

# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import date

from .chat_utils import add_system_style_message, get_or_create_conversation_for_users
from .models import DirectHire, Conversation, Message
from .forms import DirectHireForm, MessageForm
from .notifications import notify_direct_hire


def _conversation_cards_html(request, conversations):
    return render_to_string(
        'partials/conversation_cards.html',
        {
            'conversations': conversations,
            'request': request,
        },
        request=request,
    )

@login_required
def hire_artisan(request, artisan_id):
    artisan = get_object_or_404(CustomUser, id=artisan_id, user_type='artisan')
    
    if request.method == 'POST':
        form = DirectHireForm(request.POST)
        if form.is_valid():
            direct_hire = form.save(commit=False)
            direct_hire.client = request.user
            direct_hire.artisan = artisan
            direct_hire.save()
            
            conversation, created = get_or_create_conversation_for_users(request.user, artisan, job=None)
            if created:
                add_system_style_message(
                    conversation,
                    request.user,
                    f'Hi {artisan.display_name}, I have sent you a direct hire request for "{direct_hire.job_title}".',
                )
            
            messages.success(request, f"Your hire request has been sent to {artisan.get_full_name()}!")
            return redirect('users:direct_hire_detail', hire_id=direct_hire.id)
    else:
        form = DirectHireForm()
    
    context = {
        'artisan': artisan,
        'form': form,
    }
    return render(request, 'users/hire_artisan.html', context)

@login_required
def direct_hire_detail(request, hire_id):
    direct_hire = get_object_or_404(DirectHire, id=hire_id)
    
    # Check if user is involved in this hire
    if request.user != direct_hire.client and request.user != direct_hire.artisan:
        messages.error(request, "You don't have permission to view this hire.")
        return redirect('users:dashboard')
    
    # Get or create conversation
    counterpart = direct_hire.artisan if request.user == direct_hire.client else direct_hire.client
    conversation, _ = get_or_create_conversation_for_users(request.user, counterpart, job=None)
    
    if request.method == 'POST' and 'action' in request.POST:
        action = request.POST.get('action')
        if action == 'accept' and request.user == direct_hire.artisan:
            direct_hire.status = 'accepted'
            direct_hire.save()
            messages.success(request, "You've accepted the hire request!")
        elif action == 'reject' and request.user == direct_hire.artisan:
            direct_hire.status = 'rejected'
            direct_hire.save()
            messages.info(request, "You've rejected the hire request.")
        elif action == 'complete' and request.user == direct_hire.client:
            direct_hire.status = 'completed'
            direct_hire.save()
            messages.success(request, "You've marked this job as completed!")
        elif action == 'cancel':
            direct_hire.status = 'cancelled'
            direct_hire.save()
            messages.info(request, "You've cancelled the hire request.")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'status': direct_hire.get_status_display(),
                'status_key': direct_hire.status,
            })
    
    context = {
        'direct_hire': direct_hire,
        'conversation': conversation,
    }
    return render(request, 'users/direct_hire_detail.html', context)

@login_required
def notifications(request):
    conversations = Conversation.objects.filter(participants=request.user).prefetch_related('participants', 'messages').order_by('-updated_at')
    search_query = request.GET.get('q')
    if search_query:
        conversations = conversations.filter(
            Q(participants__username__icontains=search_query)
            | Q(participants__first_name__icontains=search_query)
            | Q(participants__last_name__icontains=search_query)
            | Q(messages__content__icontains=search_query)
        ).distinct()
    for conversation in conversations:
        conversation.other_user = conversation.get_other_user(request.user)
        conversation.latest_message_item = conversation.latest_message()
        conversation.unread_count = conversation.unread_count_for(request.user)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(
            {
                'success': True,
                'html': _conversation_cards_html(request, conversations),
            }
        )

    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    
    context = {
        'conversations': conversations,
        'notifications': Notification.objects.filter(user=request.user)[:10],
        'search_query': search_query or '',
    }
    return render(request, 'users/messages.html', context)


@login_required
@require_GET
def attention_summary(request):
    unread_messages = Message.objects.filter(
        conversation__participants=request.user,
        is_read=False,
    ).exclude(sender=request.user).count()
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
    unread_notifications = Notification.objects.filter(user=request.user, is_read=False).count()

    return JsonResponse({
        'unread_messages': unread_messages,
        'unread_notifications': unread_notifications,
        'attention_count': unread_messages + unread_notifications,
        'notifications': [
            {
                'title': notification.title,
                'body': notification.body,
                'action_url': notification.action_url,
                'level': notification.level,
                'created_at': notification.created_at.strftime('%b %d, %Y %I:%M %p'),
            }
            for notification in notifications
        ],
    })

@login_required
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(Conversation.objects.prefetch_related('participants', 'messages'), id=conversation_id)
    
    # Check if user is a participant
    if request.user not in conversation.participants.all():
        messages.error(request, "You don't have permission to view this conversation.")
        return redirect('users:notifications')
    
    conversation.messages.exclude(sender=request.user).update(is_read=True, read_at=timezone.now())
    
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()

            for uploaded in request.FILES.getlist('attachments'):
                MessageAttachment.objects.create(message=message, file=uploaded)
            
            conversation.updated_at = timezone.now()
            conversation.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': {
                        'id': message.id,
                        'content': message.content,
                        'timestamp': message.timestamp.strftime('%b %d, %Y %I:%M %p'),
                        'sender_name': message.sender.display_name,
                        'sender_id': message.sender_id,
                        'attachments': [
                            {'name': attachment.file.name.split('/')[-1], 'url': attachment.file.url}
                            for attachment in message.attachments.all()
                        ],
                    }
                })
            return redirect('users:conversation_detail', conversation_id=conversation.id)
    else:
        form = MessageForm()
    
    context = {
        'conversation': conversation,
        'form': form,
        'other_user': conversation.participants.exclude(id=request.user.id).first(),
    }
    return render(request, 'users/conversation_detail.html', context)

@login_required
@require_POST
def delete_conversation(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Check if user is a participant
    if request.user not in conversation.participants.all():
        messages.error(request, "You don't have permission to delete this conversation.")
        return redirect('users:notifications')
    
    conversation.delete()
    messages.success(request, "Conversation deleted successfully.")
    return redirect('users:notifications')


# views.py
def settings_view(request):
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'profile':
            # Handle profile form
            pass
        elif form_type == 'account':
            # Handle account settings form
            pass
        elif form_type == 'professional' and request.user.is_artisan:
            # Handle professional details form
            pass
        elif form_type == 'services' and request.user.is_artisan:
            # Handle services form
            pass
        elif form_type == 'preferences' and not request.user.is_artisan:
            # Handle preferences form
            pass
        
        messages.success(request, 'Settings updated successfully')
        return redirect('users:settings')
    
    # For GET requests
    categories = Category.objects.all()  # You'll need to create this model
    return render(request, 'users/settings.html', {'categories': categories})

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp import user_has_device

import base64
import qrcode
import qrcode.image.svg
from io import BytesIO

@login_required
def two_factor_setup(request):
    # Check if user already has a device
    if user_has_device(request.user):
        device = TOTPDevice.objects.get(user=request.user)
        return render(request, 'users/two_factor_manage.html', {'device': device})
    
    # Generate a new device
    device, _ = TOTPDevice.objects.get_or_create(
        user=request.user,
        name='FundiConnect Authenticator',
        defaults={'confirmed': False},
    )
    if device.confirmed:
        return render(request, 'users/two_factor_manage.html', {'device': device})
    
    # Generate provisioning URL
    url = device.config_url
    
    # Generate QR code
    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(url, image_factory=factory)
    stream = BytesIO()
    img.save(stream)
    qr_code = stream.getvalue().decode()

    if request.method == 'POST':
        token = (request.POST.get('token') or '').strip()
        if device.verify_token(token):
            if not device.confirmed:
                device.confirmed = True
                device.save(update_fields=['confirmed'])
            static_device, _ = StaticDevice.objects.get_or_create(
                user=request.user,
                name='FundiConnect Backup Codes',
                defaults={'confirmed': True},
            )
            if not static_device.token_set.exists():
                for _ in range(8):
                    StaticToken.random_token(static_device)
            messages.success(request, 'Two-factor authentication is now active on your account.')
            return redirect('users:two_factor_backup_codes')
        messages.error(request, 'That authenticator code was not valid. Please try the latest 6-digit code from your app.')
    
    return render(request, 'users/two_factor_setup.html', {
        'qr_code': qr_code,
        'secret': base64.b32encode(device.bin_key).decode('utf-8'),
        'device': device,
    })

# users/views.py
def two_factor_verify(request):
    """
    Handles 2FA token verification during login.
    """
    user_id = request.session.get('user_id_for_2fa')
    if not user_id:
        if request.user.is_authenticated:
            return redirect('users:dashboard')
        return redirect('users:login')
    
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        token = request.POST.get('token')
        device = TOTPDevice.objects.get(user=user)
        
        if device.verify_token(token):
            # Log the user in
            login(request, user)
            otp_login(request, device)
            if not device.confirmed:
                device.confirmed = True
                device.save(update_fields=['confirmed'])
            
            # Remove the session variable
            del request.session['user_id_for_2fa']
            
            # Check what step the user needs to complete
            if not user.email_verified:
                return redirect('users:verify_email')
            elif user.needs_phone_verification():
                return redirect('users:verify_phone')
            elif not user.profile_completed:
                return redirect('users:complete_profile')
            else:
                messages.success(request, "Two-factor authentication successful!")
                return redirect('users:dashboard')
        else:
            messages.error(request, "Invalid verification code.")
    
    return render(request, 'users/two_factor_verify.html', {'user': user})

@login_required
def two_factor_backup_codes(request):
    static_device, _ = StaticDevice.objects.get_or_create(
        user=request.user,
        name='FundiConnect Backup Codes',
        defaults={'confirmed': True},
    )
    backup_codes = list(static_device.token_set.values_list('token', flat=True))
    if not backup_codes:
        for _ in range(8):
            StaticToken.random_token(static_device)
        backup_codes = list(static_device.token_set.values_list('token', flat=True))
    
    if request.method == 'POST':
        return redirect('users:settings')
    
    return render(request, 'users/two_factor_backup_codes.html', {
        'backup_codes': backup_codes,
    })

@login_required
def two_factor_disable(request):
    if request.method == 'POST':
        # Verify token before disabling
        token = (request.POST.get('token') or '').strip()
        device = TOTPDevice.objects.get(user=request.user)
        static_device = StaticDevice.objects.filter(user=request.user, name='FundiConnect Backup Codes').first()
        static_token = static_device.token_set.filter(token=token).first() if static_device else None

        if device.verify_token(token) or static_token:
            if static_token:
                static_token.delete()
            device.delete()
            if static_device:
                static_device.delete()
            messages.success(request, 'Two-factor authentication has been disabled.')
            return redirect('users:settings')
        else:
            messages.error(request, 'Invalid token. Two-factor authentication remains enabled.')
    
    return render(request, 'users/two_factor_disable.html')

@login_required
def delete_account(request):
    if request.method == 'POST':
        user = request.user
        user.delete()
        messages.success(request, 'Your account has been deleted successfully.')
        return redirect('users:login')
    
    return render(request, 'users/delete_account.html')

@login_required
def complete_client_profile(request):
    if request.method == 'POST':
        form = ClientProfileForm(request.POST, request.FILES, instance=request.user.client_profile)
        if form.is_valid():
            form.save()
            request.user.profile_completed = True
            request.user.save()
            messages.success(request, 'Profile completed successfully!')
            return redirect('users:dashboard')
    else:
        form = ClientProfileForm(instance=request.user.client_profile)
    
    return render(request, 'users/complete_client_profile.html', {'form': form})

def edit_client_profile(request):
    if request.method == 'POST':
        form = ClientProfileForm(request.POST, request.FILES, instance=request.user.client_profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('users:dashboard')
    else:
        form = ClientProfileForm(instance=request.user.client_profile)
    
    return render(request, 'users/edit_client_profile.html', {'form': form})

    
