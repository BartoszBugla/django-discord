import json

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User

from chat.presence_cache import (
    clear_channel_view,
    clear_dm_view,
    touch_channel_view,
    touch_dm_view,
)
from chat.ws_broadcast import message_to_chat_group_event


def _strip_message(message):
    if not isinstance(message, str):
        return None
    stripped = message.strip()
    return stripped if stripped else None


def _parse_message_id(raw):
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


@database_sync_to_async
def _delete_channel_message_if_allowed(user_id, message_id, channel_id):
    from django.contrib.auth.models import User

    from chat.models import Message, Profile

    user = User.objects.get(pk=user_id)
    msg = Message.objects.filter(pk=message_id, channel_id=channel_id).first()
    if msg is None:
        return False, "not_found"
    profile, _ = Profile.objects.get_or_create(user=user)
    is_mod = profile.role in ("admin", "moderator") or user.is_superuser
    if msg.autor_id != user_id and not is_mod:
        return False, "forbidden"
    msg.delete()
    return True, None


@database_sync_to_async
def _delete_dm_message_if_allowed(user_id, message_id, peer_user_id):
    from django.contrib.auth.models import User
    from django.db.models import Q

    from chat.models import Message, Profile

    user = User.objects.get(pk=user_id)
    peer = int(peer_user_id)
    msg = (
        Message.objects.filter(pk=message_id, channel__isnull=True)
        .filter(
            Q(autor_id=user_id, odbiorca_id=peer) | Q(autor_id=peer, odbiorca_id=user_id)
        )
        .first()
    )
    if msg is None:
        return False, "not_found"
    profile, _ = Profile.objects.get_or_create(user=user)
    is_mod = profile.role in ("admin", "moderator") or user.is_superuser
    if msg.autor_id != user_id and not is_mod:
        return False, "forbidden"
    msg.delete()
    return True, None


@database_sync_to_async
def _user_is_channel_member(user_id, channel_id):
    from chat.models import ChannelMember

    return ChannelMember.objects.filter(user_id=user_id, channel_id=channel_id).exists()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return
        if not user.is_active:
            await self.close()
            return
        self.channel_id = int(self.scope["url_route"]["kwargs"]["channel_id"])
        if not await _user_is_channel_member(user.id, self.channel_id):
            await self.close()
            return
        self.room_group_name = f"chat_{self.channel_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await sync_to_async(touch_channel_view)(user.id, self.channel_id)

    async def disconnect(self, close_code):
        user = self.scope.get("user")
        if (
            user
            and not user.is_anonymous
            and getattr(self, "channel_id", None) is not None
        ):
            await sync_to_async(clear_channel_view)(user.id, self.channel_id)
        if getattr(self, "room_group_name", None):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return
        user = self.scope["user"]

        if user.is_anonymous:
            return
        if not user.is_active:
            return
        if not getattr(self, "room_group_name", None):
            return

        if data.get("type") == "delete":
            mid = _parse_message_id(data.get("message_id"))
            if mid is None:
                await self.send(
                    text_data=json.dumps(
                        {"type": "error", "code": "bad_message_id"}
                    )
                )
                return
            ok, err = await _delete_channel_message_if_allowed(
                user.id, mid, self.channel_id
            )
            if ok:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {"type": "message_deleted", "message_id": mid},
                )
            else:
                await self.send(
                    text_data=json.dumps({"type": "error", "code": err or "forbidden"})
                )
            return

        message = _strip_message(data.get("message", ""))
        if message is None:
            return

        msg = await self.save_message(user, self.channel_id, message)
        await sync_to_async(touch_channel_view)(user.id, self.channel_id)

        payload = await sync_to_async(message_to_chat_group_event)(msg)
        await self.channel_layer.group_send(self.room_group_name, payload)

        from chat.inbox_notify import notify_channel_message_saved

        await sync_to_async(notify_channel_message_saved, thread_sensitive=True)(msg)

    async def message_deleted(self, event):
        user = self.scope["user"]
        if not user.is_anonymous:
            await sync_to_async(touch_channel_view)(user.id, self.channel_id)
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_deleted",
                    "message_id": event["message_id"],
                }
            )
        )

    async def chat_message(self, event):
        if event.get("message") is None and not (
            event.get("image_url") or event.get("audio_url")
        ):
            return
        user = self.scope["user"]
        if not user.is_anonymous:
            await sync_to_async(touch_channel_view)(user.id, self.channel_id)

        await self.send(
            text_data=json.dumps(
                {
                    "message": event.get("message", "") or "",
                    "username": event["username"],
                    "timestamp": event["timestamp"],
                    "message_id": event["message_id"],
                    "author_id": event.get("author_id"),
                    "author_role": event.get("author_role") or "user",
                    "image_url": event.get("image_url") or "",
                    "audio_url": event.get("audio_url") or "",
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
        if not user.is_active:
            await self.close()
            return

        other_id = int(self.other_user_id)

        ids = sorted([user.id, other_id])
        self.room_group_name = f"dm_{ids[0]}_{ids[1]}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await sync_to_async(touch_dm_view)(user.id, other_id)

    async def disconnect(self, close_code):
        user = self.scope.get("user")
        if user and not user.is_anonymous and hasattr(self, "other_user_id"):
            await sync_to_async(clear_dm_view)(user.id, int(self.other_user_id))
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return
        user = self.scope["user"]

        if user.is_anonymous:
            return
        if not user.is_active:
            return
        if not getattr(self, "room_group_name", None):
            return

        if data.get("type") == "delete":
            mid = _parse_message_id(data.get("message_id"))
            if mid is None:
                await self.send(
                    text_data=json.dumps(
                        {"type": "error", "code": "bad_message_id"}
                    )
                )
                return
            ok, err = await _delete_dm_message_if_allowed(
                user.id, mid, self.other_user_id
            )
            if ok:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {"type": "message_deleted", "message_id": mid},
                )
            else:
                await self.send(
                    text_data=json.dumps({"type": "error", "code": err or "forbidden"})
                )
            return

        message = _strip_message(data.get("message", ""))
        if message is None:
            return

        msg = await self.save_dm(user, self.other_user_id, message)
        await sync_to_async(touch_dm_view)(user.id, int(self.other_user_id))

        payload = await sync_to_async(message_to_chat_group_event)(msg)
        await self.channel_layer.group_send(self.room_group_name, payload)

        from chat.inbox_notify import notify_dm_message_saved

        await sync_to_async(notify_dm_message_saved, thread_sensitive=True)(msg)

    async def message_deleted(self, event):
        user = self.scope["user"]
        if not user.is_anonymous:
            await sync_to_async(touch_dm_view)(user.id, int(self.other_user_id))
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_deleted",
                    "message_id": event["message_id"],
                }
            )
        )

    async def chat_message(self, event):
        if event.get("message") is None and not (
            event.get("image_url") or event.get("audio_url")
        ):
            return
        user = self.scope["user"]
        if not user.is_anonymous:
            await sync_to_async(touch_dm_view)(user.id, int(self.other_user_id))

        await self.send(
            text_data=json.dumps(
                {
                    "message": event.get("message", "") or "",
                    "username": event["username"],
                    "timestamp": event["timestamp"],
                    "message_id": event["message_id"],
                    "author_id": event.get("author_id"),
                    "author_role": event.get("author_role") or "user",
                    "image_url": event.get("image_url") or "",
                    "audio_url": event.get("audio_url") or "",
                }
            )
        )

    @database_sync_to_async
    def save_dm(self, user, other_user_id, tresc):
        from chat.models import Message

        oid = int(other_user_id)
        odbiorca = User.objects.get(id=oid)
        return Message.objects.create(autor=user, odbiorca=odbiorca, tresc=tresc)


class UserInboxConsumer(AsyncWebsocketConsumer):
    """Push events for browser notifications (new DM / new message in other channel)."""

    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return
        if not user.is_active:
            await self.close()
            return
        self.group_name = f"inbox_user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def inbox_notify(self, event):
        await self.send(text_data=json.dumps(event["data"]))


class PresenceConsumer(AsyncWebsocketConsumer):
    """Heartbeat: client sends {"type": "ping"} every ~10s; we refresh last_seen_at."""

    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return
        if not user.is_active:
            await self.close()
            return
        await self.accept()
        await self.touch_presence(user.id)

    async def disconnect(self, close_code):
        return

    async def receive(self, text_data):
        user = self.scope["user"]
        if user.is_anonymous:
            return
        if not user.is_active:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return
        if data.get("type") == "ping":
            await self.touch_presence(user.id)
            await self.send(text_data=json.dumps({"type": "pong"}))

    @database_sync_to_async
    def touch_presence(self, user_id):
        from django.utils import timezone

        from chat.models import Profile

        user = User.objects.get(pk=user_id)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.last_seen_at = timezone.now()
        profile.is_online = True
        profile.save(update_fields=["last_seen_at", "is_online"])
