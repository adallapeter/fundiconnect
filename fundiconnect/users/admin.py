from django.contrib import admin
from .models import (
    ArtisanProfile,
    AssistantChat,
    Certification,
    ClientProfile,
    Conversation,
    CustomUser,
    DirectHire,
    Message,
    MessageAttachment,
    Notification,
    PortfolioImage,
    ReputationBadge,
)

admin.site.register(CustomUser)
admin.site.register(ClientProfile)
admin.site.register(ArtisanProfile)
admin.site.register(PortfolioImage)
admin.site.register(Certification)
admin.site.register(ReputationBadge)
admin.site.register(DirectHire)
admin.site.register(Conversation)
admin.site.register(Message)
admin.site.register(MessageAttachment)
admin.site.register(Notification)
admin.site.register(AssistantChat)
