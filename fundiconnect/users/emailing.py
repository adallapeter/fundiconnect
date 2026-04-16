import logging
from urllib.parse import urljoin

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


def absolute_url(path: str = '') -> str:
    base = getattr(settings, 'SITE_URL', '').rstrip('/')
    if not base:
        host = (settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS[0] != '*' else 'http://127.0.0.1:8000')
        if not host.startswith('http'):
            host = f'https://{host}'
        base = host.rstrip('/')
    path = path if path.startswith('/') else f'/{path}'
    return urljoin(f'{base}/', path.lstrip('/'))


def send_brevo_email(*, to_email: str, to_name: str, subject: str, html_content: str, text_content: str = '') -> bool:
    api_key = getattr(settings, 'BREVO_API_KEY', '')
    sender_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '')
    sender_name = getattr(settings, 'EMAIL_SENDER_NAME', 'FundiConnect')
    smtp_host_user = getattr(settings, 'EMAIL_HOST_USER', '')
    smtp_host_password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')

    if not to_email:
        logger.warning('Email send skipped because no recipient email was provided.')
        return False

    if not sender_email:
        logger.warning('Email send skipped because DEFAULT_FROM_EMAIL is not configured.')
        return False

    if api_key:
        payload = {
            'sender': {'email': sender_email, 'name': sender_name},
            'to': [{'email': to_email, 'name': to_name or to_email}],
            'subject': subject,
            'htmlContent': html_content,
            'textContent': text_content or subject,
        }
        try:
            response = requests.post(
                'https://api.brevo.com/v3/smtp/email',
                headers={
                    'accept': 'application/json',
                    'api-key': api_key,
                    'content-type': 'application/json',
                },
                json=payload,
                timeout=20,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as exc:
            logger.exception('Brevo email send failed: %s', exc)

    if not smtp_host_user or not smtp_host_password:
        logger.warning(
            'Email send skipped after Brevo attempt because SMTP credentials are not configured. '
            'Set BREVO_API_KEY or EMAIL_HOST_USER/EMAIL_HOST_PASSWORD.'
        )
        return False

    try:
        from django.core.mail import EmailMultiAlternatives

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content or subject,
            from_email=sender_email,
            to=[to_email],
        )
        if html_content:
            email.attach_alternative(html_content, 'text/html')
        email.send(fail_silently=False)
        return True
    except Exception as exc:
        logger.exception('SMTP fallback email send failed: %s', exc)
        return False
