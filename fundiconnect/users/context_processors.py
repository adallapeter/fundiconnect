from django_otp import user_has_device


def two_factor_status(request):
    context = {
        "user_has_2fa": False,
        "unread_message_count": 0,
        "unread_notification_count": 0,
        "attention_count": 0,
    }

    if not request.user.is_authenticated:
        return context

    context["user_has_2fa"] = user_has_device(request.user)

    from .models import Message, Notification

    context["unread_message_count"] = Message.objects.filter(
        conversation__participants=request.user,
        is_read=False,
    ).exclude(sender=request.user).count()
    context["unread_notification_count"] = Notification.objects.filter(user=request.user, is_read=False).count()
    context["attention_count"] = context["unread_message_count"] + context["unread_notification_count"]
    return context
