from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import PasswordResetForm
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import CustomUser, ArtisanProfile, PortfolioImage, Certification, ClientProfile
from .emailing import send_brevo_email


def _location_attrs(label, default='Nairobi, Kenya', hide_map='0'):
    return {
        'data-location-picker': '1',
        'data-location-label': label,
        'data-location-default': default,
        'data-location-hide-map': hide_map,
        'autocomplete': 'off',
    }


class CustomUserCreationForm(UserCreationForm):
    user_type = forms.ChoiceField(choices=CustomUser.USER_TYPE_CHOICES)
    
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'phone_number', 'user_type', 'password1', 'password2')


class BrevoPasswordResetForm(PasswordResetForm):
    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        subject = render_to_string(subject_template_name, context).strip().replace('\n', '')
        text_content = render_to_string(email_template_name, context)
        html_content = (
            render_to_string(html_email_template_name, context)
            if html_email_template_name
            else text_content.replace('\n', '<br>')
        )
        send_brevo_email(
            to_email=to_email,
            to_name=context.get('user').display_name if context.get('user') else '',
            subject=subject,
            html_content=html_content,
            text_content=strip_tags(text_content) if '<' in text_content else text_content,
        )


class ArtisanProfileForm(forms.ModelForm):
    class Meta:
        model = ArtisanProfile
        fields = [
            'full_name', 'profile_picture', 'category', 'specialization', 
            'description', 'experience_level', 'hourly_rate', 'availability', 'location'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'location': forms.TextInput(attrs=_location_attrs('service area')),
        }
        help_texts = {
            'hourly_rate': 'Enter your hourly rate in your local currency',
            'location': 'Enter the areas where you provide services',
            'service_radius': 'Enter the radius of your service area in kilometers',
            'category': 'Select the categories that best describe your services',
        }


class PortfolioImageForm(forms.ModelForm):
    class Meta:
        model = PortfolioImage
        fields = ['image', 'caption']


class CertificationForm(forms.ModelForm):
    class Meta:
        model = Certification
        fields = ['name', 'issuing_organization', 'issue_date', 'expiration_date', 'credential_id', 'credential_url']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'expiration_date': forms.DateInput(attrs={'type': 'date'}),
        }

# forms.py
from django import forms
from .models import DirectHire, Message
from django.core.validators import MinValueValidator
from datetime import date

class DirectHireForm(forms.ModelForm):
    class Meta:
        model = DirectHire
        fields = ['job_title', 'description', 'budget', 'deadline']
        widgets = {
            'deadline': forms.DateInput(attrs={'type': 'date', 'min': date.today().isoformat()}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['budget'].validators.append(MinValueValidator(0))
        self.fields['deadline'].widget.attrs['min'] = date.today().isoformat()

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Type your message here...',
                'class': 'w-full rounded-2xl border border-slate-300 px-4 py-3 text-sm text-slate-900 outline-none focus:border-slate-500',
            }),
        }

# Add to forms.py
class ClientProfileForm(forms.ModelForm):
    class Meta:
        model = ClientProfile
        fields = ['full_name', 'profile_picture','bio', 'address', 'city']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500'}),
            'address': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500',
                **_location_attrs('address', hide_map='1'),
            }),
            'city': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500',
                **_location_attrs('city', hide_map='1'),
            }),
        }
