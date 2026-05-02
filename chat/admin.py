from django.contrib import admin
from .models import (
    Profile,
    Channel,
    ChannelMember,
    Message,
    Reaction,
    InAppNotification,
    UserReport,
)

admin.site.register(Profile)
admin.site.register(Channel)
admin.site.register(ChannelMember)
admin.site.register(Message)
admin.site.register(Reaction)
admin.site.register(InAppNotification)
admin.site.register(UserReport)
