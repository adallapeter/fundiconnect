from django.utils import timezone

from .models import Conversation, Message


def get_or_create_conversation_for_users(user_a, user_b, job=None):
    conversation = (
        Conversation.objects.filter(participants=user_a)
        .filter(participants=user_b)
        .filter(job=job)
        .first()
    )
    if conversation:
        return conversation, False

    conversation = Conversation.objects.create(job=job)
    conversation.participants.add(user_a, user_b)
    return conversation, True


def add_system_style_message(conversation, sender, content):
    message = Message.objects.create(
        conversation=conversation,
        sender=sender,
        content=content,
    )
    conversation.updated_at = timezone.now()
    conversation.save(update_fields=['updated_at'])
    return message
