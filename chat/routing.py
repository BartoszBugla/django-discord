from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/chat/(?P<channel_id>\d+)/$", consumers.ChatConsumer.as_asgi()),
    re_path(r"ws/dm/(?P<user_id>\d+)/$", consumers.DMConsumer.as_asgi()),
    re_path(r"ws/inbox/$", consumers.UserInboxConsumer.as_asgi()),
    re_path(r"ws/presence/$", consumers.PresenceConsumer.as_asgi()),
]
