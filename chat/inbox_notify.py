"""Powiadomienia inbox: zapis na liście (InAppNotification) + WebSocket do klienta."""

from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.utils import timezone

from chat.models import Channel, ChannelMember, InAppNotification


def message_push_preview(message) -> str:
    """Krótki tekst do powiadomienia (bez HTML)."""
    t = (message.tresc or "").strip()
    has_img = bool(message.obrazek)
    has_aud = bool(message.audio)
    if t:
        return t[:200]
    if has_img and has_aud:
        return "Zdjęcie i plik audio"
    if has_img:
        return "Zdjęcie"
    if has_aud:
        return "Plik audio"
    return "Nowa wiadomość"


def purge_expired_read_inapp_notifications():
    """Usuwa z bazy przeczytane powiadomienia starsze niż INAPP_NOTIFICATION_READ_RETENTION_HOURS."""
    hours = getattr(settings, "INAPP_NOTIFICATION_READ_RETENTION_HOURS", 6)
    cutoff = timezone.now() - timedelta(hours=hours)
    deleted_count, _ = InAppNotification.objects.filter(
        read_at__isnull=False, read_at__lt=cutoff
    ).delete()
    return deleted_count


def _layer_send(group, payload):
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        group,
        {"type": "inbox_notify", "data": payload},
    )


def notify_channel_message_saved(message):
    """Po zapisie wiadomości na kanale — lista + WS dla pozostałych członków."""
    cid = message.channel_id
    if cid is None:
        return
    ch_name = Channel.objects.filter(pk=cid).values_list("nazwa", flat=True).first() or ""
    recipient_ids = ChannelMember.objects.filter(channel_id=cid).exclude(
        user_id=message.autor_id
    ).values_list("user_id", flat=True)
    preview = message_push_preview(message)
    title = f"#{ch_name}" if ch_name else "#kanał"
    body = f"{message.autor.username}: {preview}" if preview else message.autor.username
    url = f"/kanal/{cid}/"
    if message.id:
        url += f"#message-{message.id}"

    for uid in recipient_ids:
        notif = InAppNotification.objects.create(
            user_id=uid,
            kind=InAppNotification.KIND_CHANNEL,
            title=title[:200],
            body=body[:2000],
            url=url[:500],
            channel_id=cid,
            message_id=message.id,
        )
        payload = {
            "kind": "channel",
            "channel_id": cid,
            "channel_name": ch_name,
            "from_username": message.autor.username,
            "preview": preview,
            "message_id": message.id,
            "notification_id": notif.id,
        }
        _layer_send(f"inbox_user_{uid}", payload)


def notify_dm_message_saved(message):
    """Po zapisie wiadomości DM — lista + WS dla odbiorcy."""
    if message.odbiorca_id is None:
        return
    preview = message_push_preview(message)
    title = f"Wiadomość od {message.autor.username}"
    body = preview or "Nowa wiadomość"
    url = f"/dm/{message.autor_id}/"
    if message.id:
        url += f"#message-{message.id}"

    notif = InAppNotification.objects.create(
        user_id=message.odbiorca_id,
        kind=InAppNotification.KIND_DM,
        title=title[:200],
        body=body[:2000],
        url=url[:500],
        dm_from_user_id=message.autor_id,
        message_id=message.id,
    )
    payload = {
        "kind": "dm",
        "from_user_id": message.autor_id,
        "from_username": message.autor.username,
        "preview": preview,
        "message_id": message.id,
        "notification_id": notif.id,
    }
    _layer_send(f"inbox_user_{message.odbiorca_id}", payload)
