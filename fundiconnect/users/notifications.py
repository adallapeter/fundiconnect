from django.utils import timezone

from .emailing import absolute_url, send_brevo_email
from .models import Notification


def create_notification(*, user, title, body, level='info', action_url='', email_subject=None, email_html=None, email_text=None):
    notification = Notification.objects.create(
        user=user,
        title=title,
        body=body,
        level=level,
        action_url=action_url,
    )

    if user.email and (email_subject or email_html or email_text):
        sent = send_brevo_email(
            to_email=user.email,
            to_name=user.display_name,
            subject=email_subject or title,
            html_content=email_html or f'<p>{body}</p>',
            text_content=email_text or body,
        )
        if sent:
            notification.emailed_at = timezone.now()
            notification.save(update_fields=['emailed_at'])

    return notification


def send_email_verification(user, code):
    verify_url = absolute_url('/accounts/verify-email/')
    subject = 'Verify your FundiConnect email'
    body = f'Use this verification code to finish creating your account: {code}'
    html = f"""
    <div style="font-family:Arial,sans-serif;background:#f8fafc;padding:24px;">
      <div style="max-width:620px;margin:0 auto;background:#ffffff;border-radius:20px;padding:32px;border:1px solid #e2e8f0;">
        <h1 style="margin:0 0 16px;color:#0f172a;">Verify your email</h1>
        <p style="color:#475569;line-height:1.7;">Hi {user.display_name}, use the code below to verify your FundiConnect account.</p>
        <div style="margin:24px 0;padding:20px;border-radius:18px;background:linear-gradient(135deg,#0f172a,#475569);color:#ffffff;font-size:28px;font-weight:800;letter-spacing:0.1em;text-align:center;">{code}</div>
        <p style="color:#475569;line-height:1.7;">Open <a href="{verify_url}" style="color:#0f172a;font-weight:700;">{verify_url}</a> to complete verification.</p>
      </div>
    </div>
    """
    return send_brevo_email(
        to_email=user.email,
        to_name=user.display_name,
        subject=subject,
        html_content=html,
        text_content=f'{body}\n\nVerify here: {verify_url}',
    )


def notify_bid_received(bid):
    action_url = f'/jobs/job/{bid.job_id}/'
    create_notification(
        user=bid.job.client,
        title='New bid received',
        body=f'{bid.artisan.user.display_name} placed a bid on "{bid.job.title}".',
        level='info',
        action_url=action_url,
        email_subject=f'New bid for {bid.job.title}',
        email_html=f'<p>{bid.artisan.user.display_name} placed a bid on <strong>{bid.job.title}</strong>.</p><p><a href="{absolute_url(action_url)}">Review the bid</a></p>',
        email_text=f'{bid.artisan.user.display_name} placed a bid on {bid.job.title}. Review it at {absolute_url(action_url)}',
    )


def notify_bid_status(bid, accepted=False):
    title = 'Bid accepted' if accepted else 'Bid update'
    body = f'Your bid for "{bid.job.title}" was {"accepted" if accepted else bid.get_status_display().lower()}.'
    create_notification(
        user=bid.artisan.user,
        title=title,
        body=body,
        level='success' if accepted else 'warning',
        action_url=f'/jobs/job/{bid.job_id}/',
        email_subject=title,
        email_html=f'<p>{body}</p><p><a href="{absolute_url(f"/jobs/job/{bid.job_id}/")}">Open the job workspace</a></p>',
        email_text=f'{body} Visit {absolute_url(f"/jobs/job/{bid.job_id}/")}',
    )


def notify_direct_hire(direct_hire, recipient, title, body, level='info'):
    create_notification(
        user=recipient,
        title=title,
        body=body,
        level=level,
        action_url=f'/accounts/direct-hire/{direct_hire.id}/',
        email_subject=title,
        email_html=f'<p>{body}</p><p><a href="{absolute_url(f"/accounts/direct-hire/{direct_hire.id}/")}">Open direct hire</a></p>',
        email_text=f'{body} Open {absolute_url(f"/accounts/direct-hire/{direct_hire.id}/")}',
    )


def notify_new_message(message):
    for participant in message.conversation.participants.exclude(id=message.sender_id):
        create_notification(
            user=participant,
            title='New message',
            body=f'{message.sender.display_name} sent you a new message.',
            level='info',
            action_url=f'/accounts/messages/{message.conversation_id}/',
            email_subject='New message on FundiConnect',
            email_html=f'<p>{message.sender.display_name} sent you a new message.</p><p><a href="{absolute_url(f"/accounts/messages/{message.conversation_id}/")}">Open conversation</a></p>',
            email_text=f'{message.sender.display_name} sent you a new message. Open {absolute_url(f"/accounts/messages/{message.conversation_id}/")}',
        )


def notify_review_received(review):
    create_notification(
        user=review.recipient,
        title='New review received',
        body=f'{review.author.display_name} left a {review.rating}/5 review on "{review.job.title}".',
        level='success',
        action_url=f'/jobs/reviews/user/{review.recipient_id}/',
        email_subject='You received a new review',
        email_html=f'<p>{review.author.display_name} left a {review.rating}/5 review on <strong>{review.job.title}</strong>.</p><p><a href="{absolute_url(f"/jobs/reviews/user/{review.recipient_id}/")}">Read the review</a></p>',
        email_text=f'You received a new review from {review.author.display_name}. See {absolute_url(f"/jobs/reviews/user/{review.recipient_id}/")}',
    )
