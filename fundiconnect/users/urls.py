# users/urls.py
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
from .forms import BrevoPasswordResetForm

app_name = 'users'


urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('profile/<int:pk>/', views.profile, name='profile'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification_email'),
    path('verify-phone/', views.verify_phone, name='verify_phone'),
    path('send-phone-verification/', views.send_phone_verification, name='send_phone_verification'),
    path('skip-phone-verification/', views.skip_phone_verification, name='skip_phone_verification'),
    path('complete-profile/', views.complete_profile, name='complete_profile'),
    path('edit-profile/', views.edit_client_profile, name='edit_client_profile'),
    path('artisan/profile/complete/', views.complete_artisan_profile, name='complete_artisan_profile'),
    path('artisan/profile/edit/', views.edit_artisan_profile, name='edit_artisan_profile'),
    path('artisans/', views.artisans, name='artisans'),
    path('artisans/filter/', views.artisan_list_ajax, name='artisan_list_ajax'), 
    path('artisan/<int:artisan_id>/', views.artisan_detail, name='artisan_detail'),
    path('artisan/<int:artisan_user_id>/reviews/', views.artisan_reviews_ajax, name='artisan_reviews_ajax'),
    
    path('portfolio/delete/<int:pk>/', views.delete_portfolio_image, name='delete_portfolio_image'),
    path('certification/delete/<int:pk>/', views.delete_certification, name='delete_certification'),
    path('artisan/hire/<int:artisan_id>/', views.hire_artisan, name='hire_artisan'),
    path('direct-hire/<int:hire_id>/', views.direct_hire_detail, name='direct_hire_detail'),
    path('notifications/', views.notifications, name='notifications'),
    path('attention/summary/', views.attention_summary, name='attention_summary'),
    path('messages/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
    path('messages/<int:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),
    path('settings/', views.settings_view, name='settings'),
    path('assistant/respond/', views.assistant_respond, name='assistant_respond'),
    path('location/search/', views.location_search, name='location_search'),
    path('location/reverse/', views.location_reverse, name='location_reverse'),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='users/password_reset_form.html',
            form_class=BrevoPasswordResetForm,
            email_template_name='users/password_reset_email.txt',
            subject_template_name='users/password_reset_subject.txt',
            success_url='/accounts/password-reset/done/',
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(template_name='users/password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='users/password_reset_confirm.html',
            success_url='/accounts/reset/done/',
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(template_name='users/password_reset_complete.html'),
        name='password_reset_complete',
    ),
    path(
        'password-change/',
        auth_views.PasswordChangeView.as_view(
            template_name='users/password_change_form.html',
            success_url='/accounts/password-change/done/',
        ),
        name='password_change',
    ),
    path(
        'password-change/done/',
        auth_views.PasswordChangeDoneView.as_view(template_name='users/password_change_done.html'),
        name='password_change_done',
    ),
    path('two-factor/setup/', views.two_factor_setup, name='two_factor_setup'),
    path('two-factor/verify/', views.two_factor_verify, name='two_factor_verify'),
    path('two-factor/backup-codes/', views.two_factor_backup_codes, name='two_factor_backup_codes'),
    path('two-factor/disable/', views.two_factor_disable, name='two_factor_disable'),
    path('delete-account/', views.delete_account, name='delete_account'),
]
