import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User


def _strip_message(message):
    if not isinstance(message, str):
        return None
    stripped = message.strip()
    return stripped if stripped else None


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.channel_id = self.scope["url_route"]["kwargs"]["channel_id"]
        self.room_group_name = f"chat_{self.channel_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = _strip_message(data.get("message", ""))
        user = self.scope["user"]

        if user.is_anonymous:
            return
        if message is None:
            return

        msg = await self.save_message(user, self.channel_id, message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "username": user.username,
                "timestamp": msg.timestamp.strftime("%H:%M"),
                "message_id": msg.id,
            },
        )

    async def chat_message(self, event):
        if event["message"] is None:
            return

        await self.send(
            text_data=json.dumps(
                {
                    "message": event["message"],
                    "username": event["username"],
                    "timestamp": event["timestamp"],
                    "message_id": event["message_id"],
                }
            )
        )

    @database_sync_to_async
    def save_message(self, user, channel_id, tresc):
        from chat.models import Message, Channel

        channel = Channel.objects.get(id=channel_id)
        return Message.objects.create(autor=user, channel=channel, tresc=tresc)


class DMConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.other_user_id = self.scope["url_route"]["kwargs"]["user_id"]
        user = self.scope["user"]

        if user.is_anonymous:
            await self.close()
            return

        ids = sorted([user.id, int(self.other_user_id)])
        self.room_group_name = f"dm_{ids[0]}_{ids[1]}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = _strip_message(data.get("message", ""))
        user = self.scope["user"]

        if user.is_anonymous:
            return
        if message is None:
            return

        msg = await self.save_dm(user, self.other_user_id, message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "username": user.username,
                "timestamp": msg.timestamp.strftime("%H:%M"),
                "message_id": msg.id,
            },
        )

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "message": event["message"],
                    "username": event["username"],
                    "timestamp": event["timestamp"],
                    "message_id": event["message_id"],
                }
            )
        )

    @database_sync_to_async
    def save_dm(self, user, other_user_id, tresc):
        from chat.models import Message

        odbiorca = User.objects.get(id=other_user_id)
        return Message.objects.create(autor=user, odbiorca=odbiorca, tresc=tresc)
