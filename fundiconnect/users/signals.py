from django.db.models.signals import post_save
from django.dispatch import receiver

from jobs.models import Bid, Job, Reviews
from django.db.models import Avg

from .models import DirectHire, Message
from .notifications import (
    notify_bid_received,
    notify_bid_status,
    notify_direct_hire,
    notify_new_message,
    notify_review_received,
)


@receiver(post_save, sender=Bid)
def bid_notifications(sender, instance, created, **kwargs):
    if created:
        notify_bid_received(instance)
        return

    if instance.status == 'accepted':
        notify_bid_status(instance, accepted=True)
    elif instance.status in ['rejected', 'withdrawn']:
        notify_bid_status(instance, accepted=False)


@receiver(post_save, sender=DirectHire)
def direct_hire_notifications(sender, instance, created, **kwargs):
    if created:
        notify_direct_hire(
            instance,
            instance.artisan,
            'New direct hire request',
            f'{instance.client.display_name} sent you a direct hire request for "{instance.job_title}".',
            'urgent',
        )
        return

    if instance.status == 'accepted':
        notify_direct_hire(instance, instance.client, 'Hire request accepted', f'{instance.artisan.display_name} accepted your direct hire request.', 'success')
    elif instance.status == 'rejected':
        notify_direct_hire(instance, instance.client, 'Hire request rejected', f'{instance.artisan.display_name} rejected your direct hire request.', 'warning')
    elif instance.status == 'completed':
        notify_direct_hire(instance, instance.artisan, 'Direct hire completed', f'{instance.client.display_name} marked "{instance.job_title}" as completed.', 'success')
    elif instance.status == 'cancelled':
        notify_direct_hire(instance, instance.artisan, 'Direct hire cancelled', f'{instance.client.display_name} cancelled the direct hire request for "{instance.job_title}".', 'warning')


@receiver(post_save, sender=Message)
def message_notifications(sender, instance, created, **kwargs):
    if created:
        notify_new_message(instance)


@receiver(post_save, sender=Reviews)
def review_notifications(sender, instance, created, **kwargs):
    if created and instance.recipient:
        notify_review_received(instance)
        if getattr(instance.recipient, 'is_artisan', False) and hasattr(instance.recipient, 'artisan_profile'):
            artisan_profile = instance.recipient.artisan_profile
            artisan_reviews = Reviews.objects.filter(recipient=instance.recipient, review_type='client_to_artisan')
            artisan_profile.rating = artisan_reviews.aggregate(avg=Avg('rating'))['avg'] or 0
            artisan_profile.completed_projects = Job.objects.filter(
                artisan=instance.recipient,
                status__in=['completed', 'closed'],
            ).distinct().count()
            artisan_profile.save(update_fields=['rating', 'completed_projects', 'updated_at'])
