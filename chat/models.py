from datetime import timedelta

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

HEARTBEAT_ONLINE_SECONDS = 30


ROLE_CHOICES = [
    ("admin", "Administrator"),
    ("moderator", "Moderator"),
    ("user", "Użytkownik"),
]


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    opis = models.TextField(blank=True, default="")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="user")
    is_online = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def appears_online(self):
        """True if the browser sent a presence ping within HEARTBEAT_ONLINE_SECONDS."""
        if self.last_seen_at is None:
            return False
        return timezone.now() - self.last_seen_at <= timedelta(
            seconds=HEARTBEAT_ONLINE_SECONDS
        )


class Channel(models.Model):
    nazwa = models.CharField(max_length=100)
    opis = models.TextField(blank=True, default="")
    tworca = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_channels"
    )
    data_utworzenia = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nazwa


class ChannelMember(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name="members"
    )
    data_dolaczenia = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "channel")

    def __str__(self):
        return f"{self.user.username} w {self.channel.nazwa}"


class Message(models.Model):
    autor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages")
    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="messages",
    )
    odbiorca = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="received_messages",
    )
    tresc = models.TextField(blank=True, default="")
    obrazek = models.ImageField(upload_to="obrazki/", blank=True, null=True)
    audio = models.FileField(upload_to="audio/", blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        if self.channel:
            return f"{self.autor.username} w {self.channel.nazwa}: {self.tresc[:30]}"
        return f"{self.autor.username} -> {self.odbiorca.username}: {self.tresc[:30]}"


class Reaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="reactions"
    )
    emoji = models.CharField(max_length=10)

    class Meta:
        unique_together = ("user", "message", "emoji")

    def __str__(self):
        return f"{self.user.username} -> {self.emoji}"
