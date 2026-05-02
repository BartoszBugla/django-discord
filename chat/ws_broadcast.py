"""Broadcast wiadomości czatu do grup Channels (payload z URL-ami mediów, bez binariów)."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone as dj_tz


def format_chat_timestamp(ts):
    return dj_tz.localtime(ts).strftime("%d.%m.%Y %H:%M")


def message_ws_payload(message):
    """Ten sam kształt JSON co wysyła consumer do przeglądarki (bez pola ``type`` grupy)."""
    from chat.models import Profile

    profile, _ = Profile.objects.get_or_create(user_id=message.autor_id)
    return {
        "message": (message.tresc or "").strip(),
        "username": message.autor.username,
        "timestamp": format_chat_timestamp(message.timestamp),
        "message_id": message.id,
        "author_id": message.autor_id,
        "author_role": profile.role,
        "image_url": message.obrazek.url if message.obrazek else "",
        "audio_url": message.audio.url if message.audio else "",
    }


def message_to_chat_group_event(message):
    payload = message_ws_payload(message)
    payload["type"] = "chat_message"
    return payload


def broadcast_chat_room_message(message):
    layer = get_channel_layer()
    if layer is None:
        return
    payload = message_to_chat_group_event(message)
    if message.channel_id:
        group = f"chat_{message.channel_id}"
    else:
        a, b = sorted([message.autor_id, message.odbiorca_id])
        group = f"dm_{a}_{b}"
    async_to_sync(layer.group_send)(group, payload)
