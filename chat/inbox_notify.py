"""Powiadomienia inbox (Channels): podglad wiadomosci + push do grup uzytkownikow."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def message_push_preview(message) -> str:
    """Krotki tekst do powiadomienia push (bez HTML)."""
    t = (message.tresc or "").strip()
    has_img = bool(message.obrazek)
    has_aud = bool(message.audio)
    if t:
        return t[:200]
    if has_img and has_aud:
        return "Zdjecie i plik audio"
    if has_img:
        return "Zdjecie"
    if has_aud:
        return "Plik audio"
    return "Nowa wiadomosc"


def _layer_send(group, payload):
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        group,
        {"type": "inbox_notify", "data": payload},
    )


def notify_channel_message_saved(message):
    """Po zapisie wiadomosci na kanale (np. formularz HTTP) — powiadom innych czlonkow."""
    from chat.models import Channel, ChannelMember

    cid = message.channel_id
    if cid is None:
        return
    ch_name = Channel.objects.filter(pk=cid).values_list("nazwa", flat=True).first() or ""
    recipient_ids = ChannelMember.objects.filter(channel_id=cid).exclude(
        user_id=message.autor_id
    ).values_list("user_id", flat=True)
    preview = message_push_preview(message)
    payload = {
        "kind": "channel",
        "channel_id": cid,
        "channel_name": ch_name,
        "from_username": message.autor.username,
        "preview": preview,
        "message_id": message.id,
    }
    for uid in recipient_ids:
        _layer_send(f"inbox_user_{uid}", payload)


def notify_dm_message_saved(message):
    """Po zapisie wiadomosci DM (np. formularz HTTP)."""
    if message.odbiorca_id is None:
        return
    preview = message_push_preview(message)
    payload = {
        "kind": "dm",
        "from_user_id": message.autor_id,
        "from_username": message.autor.username,
        "preview": preview,
        "message_id": message.id,
    }
    _layer_send(f"inbox_user_{message.odbiorca_id}", payload)
