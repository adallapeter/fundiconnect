# users/middleware.py
from django.shortcuts import redirect
from django.urls import reverse, resolve
from django.utils.deprecation import MiddlewareMixin

class ArtisanProfileCompletionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Check if user is authenticated and is an artisan
        if (request.user.is_authenticated and 
            request.user.is_artisan and 
            not request.user.profile_completed and
            request.path not in [reverse('users:complete_artisan_profile'), 
                                reverse('users:edit_artisan_profile'),
                                reverse('users:logout')] and
            not request.path.startswith('/admin/')):
            return redirect('users:complete_artisan_profile')
        
        return response


class VerificationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Skip middleware for static files, media, and API endpoints
        if (request.path.startswith('/static/') or 
            request.path.startswith('/media/') or 
            request.path.startswith('/api/') or
            request.path.startswith('/admin/')):
            return None
        
        # Skip middleware for unauthenticated users
        if not request.user.is_authenticated:
            return None
        
        # Skip middleware for admin users
        if request.user.is_staff or request.user.is_superuser:
            return None
        
        # Get the URL name for the current path
        try:
            current_url_name = resolve(request.path).url_name
        except:
            current_url_name = None
        
        # List of URL names that don't require verification
        exempt_url_names = [
            'logout',
            'verify_email',
            'verify_phone',
            'resend_verification_email',
            'send_phone_verification',
            'skip_phone_verification',
            'two_factor_verify',
            'two_factor_setup',
            'two_factor_backup_codes',
            'two_factor_disable',
            'complete_profile',
            'complete_artisan_profile',
            'edit_artisan_profile',
            'complete_client_profile',
            'edit_client_profile',
            'admin',
            'admin:index',
            'admin:login',
            'admin:logout',
            'admin:password_change',
            'admin:password_change_done',
            'password_change',
            'password_change_done',
            'password_reset',
            'password_reset_done',
            'password_reset_confirm',
            'password_reset_complete',
        ]
        
        # Check if current URL is exempt
        if current_url_name in exempt_url_names:
            return None
        
        # Redirect to email verification if not verified
        if not request.user.email_verified and current_url_name != 'verify_email':
            return redirect('users:verify_email')
        
        # Redirect to phone verification if email is verified but phone is not
        if (request.user.email_verified and 
            request.user.needs_phone_verification() and 
            current_url_name != 'verify_phone'):
            return redirect('users:verify_phone')
        
        # Redirect to profile completion if both verifications are done but profile is not complete
        if (request.user.email_verified and 
            not request.user.needs_phone_verification() and 
            not request.user.profile_completed and
            current_url_name != 'complete_profile'):
            return redirect('users:complete_profile')
        
        return None
