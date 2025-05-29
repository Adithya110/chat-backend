import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        from django.contrib.auth.models import User  
        print(f"Attempting WebSocket connection with scope: {self.scope}")
        self.other_user = self.scope['url_route']['kwargs']['username']
        self.self_user = self.scope.get("user")

        if self.self_user is None or self.self_user.is_anonymous:
            await self.close(code=4001)
            return

        self.room_name = self.get_room_name(self.self_user.username, self.other_user)
        self.room_group_name = f'chat_{self.room_name}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        from django.contrib.auth.models import User  # ✅ Safe here
        from .models import Message  # ✅ Safe here

        try:
            data = json.loads(text_data)
            message = data['message']
        except (json.JSONDecodeError, KeyError):
            await self.send(text_data=json.dumps({'error': 'Invalid message format'}))
            return

        sender = self.self_user
        receiver = await sync_to_async(User.objects.get)(username=self.other_user)

        await sync_to_async(Message.objects.create)(
            sender=sender,
            receiver=receiver,
            content=message
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender': sender.username
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender']
        }))

    def get_room_name(self, user1, user2):
        return "_".join(sorted([user1, user2]))
