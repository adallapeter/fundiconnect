from django.urls import path

from users.consumers import AssistantConsumer, ConversationConsumer


websocket_urlpatterns = [
    path('ws/conversations/<int:conversation_id>/', ConversationConsumer.as_asgi()),
    path('ws/assistant/', AssistantConsumer.as_asgi()),
]
