"""Oznacza, że użytkownik ma otwarty WebSocket czatu na danym kanale / w danej rozmowie DM (cache)."""

from django.core.cache import cache

VIEW_CHANNEL_KEY = "inview:ch:{uid}:{cid}"
VIEW_DM_KEY = "inview:dm:{uid}:{peer}"
TTL_SECONDS = 600


def touch_channel_view(user_id, channel_id):
    cache.set(
        VIEW_CHANNEL_KEY.format(uid=int(user_id), cid=int(channel_id)),
        True,
        timeout=TTL_SECONDS,
    )


def clear_channel_view(user_id, channel_id):
    cache.delete(VIEW_CHANNEL_KEY.format(uid=int(user_id), cid=int(channel_id)))


def is_viewing_channel(user_id, channel_id):
    return bool(
        cache.get(VIEW_CHANNEL_KEY.format(uid=int(user_id), cid=int(channel_id)))
    )


def touch_dm_view(user_id, peer_user_id):
    cache.set(
        VIEW_DM_KEY.format(uid=int(user_id), peer=int(peer_user_id)),
        True,
        timeout=TTL_SECONDS,
    )


def clear_dm_view(user_id, peer_user_id):
    cache.delete(VIEW_DM_KEY.format(uid=int(user_id), peer=int(peer_user_id)))


def is_viewing_dm_with(user_id, from_user_id):
    """Czy ``user_id`` ma otwartą rozmowę prywatną z ``from_user_id`` (nadawca wiadomości)."""
    return bool(
        cache.get(VIEW_DM_KEY.format(uid=int(user_id), peer=int(from_user_id)))
    )
