from django.contrib import admin
from .models import Profile, Channel, ChannelMember, Message, Reaction

admin.site.register(Profile)
admin.site.register(Channel)
admin.site.register(ChannelMember)
admin.site.register(Message)
admin.site.register(Reaction)
