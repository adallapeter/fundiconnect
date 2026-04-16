import json
import logging
import asyncio
import re

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .assistant import assistant_reply, persist_assistant_exchange
from .models import AssistantChat, Conversation, Message

logger = logging.getLogger(__name__)


class ConversationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'conversation_{self.conversation_id}'

        if not self.scope['user'].is_authenticated:
            await self.close()
            return

        has_access = await self.user_has_access()
        if not has_access:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        payload = json.loads(text_data or '{}')
        if payload.get('type') == 'typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'conversation.typing',
                    'user_id': self.scope['user'].id,
                    'user_name': self.scope['user'].display_name,
                    'is_typing': bool(payload.get('is_typing')),
                },
            )
            return
        content = (payload.get('content') or '').strip()
        if not content:
            return

        message = await self.create_message(content)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'conversation.message',
                'message': message,
            },
        )

    async def conversation_message(self, event):
        await self.send(text_data=json.dumps(event['message']))

    async def conversation_typing(self, event):
        if event['user_id'] == self.scope['user'].id:
            return
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'typing',
                    'user_id': event['user_id'],
                    'user_name': event['user_name'],
                    'is_typing': event['is_typing'],
                }
            )
        )

    @database_sync_to_async
    def user_has_access(self):
        return Conversation.objects.filter(
            id=self.conversation_id,
            participants=self.scope['user'],
        ).exists()

    @database_sync_to_async
    def create_message(self, content):
        conversation = Conversation.objects.get(id=self.conversation_id)
        message = Message.objects.create(
            conversation=conversation,
            sender=self.scope['user'],
            content=content,
        )
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=['updated_at'])

        return {
            'id': message.id,
            'content': message.content,
            'timestamp': message.timestamp.strftime('%b %d, %Y %I:%M %p'),
            'sender_id': message.sender_id,
            'sender_name': message.sender.display_name,
            'is_own': message.sender_id == self.scope['user'].id,
        }


class AssistantConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        greeting = await self.get_initial_state()
        await self.send(text_data=json.dumps({'type': 'assistant_state', 'data': greeting}))

    async def receive(self, text_data=None, bytes_data=None):
        payload = json.loads(text_data or '{}')
        if payload.get('type') == 'typing':
            await self.send(
                text_data=json.dumps(
                    {
                        'type': 'assistant_typing',
                        'is_typing': bool(payload.get('is_typing')),
                        'actor': 'user',
                    }
                )
            )
            return
        if payload.get('type') != 'generate':
            await self.send(text_data=json.dumps({'type': 'assistant_response', 'ok': False, 'error': 'Unsupported message type.'}))
            return

        prompt = (payload.get('prompt') or payload.get('content') or '').strip()
        if not prompt:
            await self.send(text_data=json.dumps({'type': 'assistant_response', 'ok': False, 'error': 'Prompt is required.'}))
            return

        user = self.scope.get('user')
        path = payload.get('path') or ''
        context = payload.get('context', None)
        # Start a periodic typing heartbeat so the client shows the assistant is working
        typing_task = None
        try:
            async def _typing_heartbeat():
                try:
                    while True:
                        await asyncio.sleep(5)
                        await self.send(text_data=json.dumps({'type': 'assistant_typing', 'is_typing': True, 'actor': 'assistant'}))
                except asyncio.CancelledError:
                    return

            typing_task = asyncio.create_task(_typing_heartbeat())

            # Run assistant generation off the event loop
            response = await sync_to_async(assistant_reply, thread_sensitive=False)(
                prompt,
                user if getattr(user, 'is_authenticated', False) else None,
                context,
                path,
            )

            # persist history (best-effort)
            try:
                await self.persist_history(prompt, response)
            except Exception:
                logger.exception('Failed to persist assistant history')

            # Stop typing heartbeat and clear typing indicator
            if typing_task:
                typing_task.cancel()
            await self.send(text_data=json.dumps({'type': 'assistant_typing', 'is_typing': False, 'actor': 'assistant'}))

            # Stream response in chunks for better UX if it's long
            try:
                text = str(response.get('text', '') if isinstance(response, dict) else '')
                if text and len(text) > 160:
                    # split on paragraphs then sentences
                    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
                    chunks = []
                    for p in paragraphs:
                        # further split into shorter pieces
                        for sent in re.split(r"(?<=[\.\!\?])\s+", p):
                            s = sent.strip()
                            if s:
                                chunks.append(s)
                    for c in chunks:
                        await self.send(text_data=json.dumps({'type': 'assistant_chunk', 'text': c}))
                        await asyncio.sleep(0.05)
            except Exception:
                logger.debug('Chunked streaming failed, falling back to single send')

            await self.send(text_data=json.dumps({'type': 'assistant_response', 'ok': True, 'data': response}))

        except Exception as exc:
            logger.exception('Assistant generation failed')
            if typing_task:
                typing_task.cancel()
            # Ensure typing indicator cleared and send an error response to the client
            try:
                await self.send(text_data=json.dumps({'type': 'assistant_typing', 'is_typing': False, 'actor': 'assistant'}))
            except Exception:
                pass
            error_payload = {'type': 'assistant_response', 'ok': False, 'error': 'Assistant generation failed.'}
            try:
                await self.send(text_data=json.dumps(error_payload))
            except Exception:
                logger.exception('Failed to send assistant error payload')

    @database_sync_to_async
    def get_initial_state(self):
        user = self.scope.get('user')
        if not getattr(user, 'is_authenticated', False):
            return {
                'greeting': 'Hello, I am the FundiConnect AI Assistant. I can help you post jobs, improve bids, and navigate the live workspace.',
                'history': [],
            }

        history = list(
            AssistantChat.objects.filter(user=user)
            .order_by('-created_at')
            .values('role', 'content')[:6]
        )[::-1]
        return {
            'greeting': f'Hello {user.display_name}, I am your FundiConnect AI Assistant. Ask for job-post help, bid coaching, or a quick account summary.',
            'history': history,
        }

    @database_sync_to_async
    def persist_history(self, prompt, response):
        user = self.scope.get('user')
        persist_assistant_exchange(user, prompt, response)
