from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from datetime import timedelta

from django.utils import timezone

from chat.inbox_notify import message_push_preview, purge_expired_read_inapp_notifications
from chat.models import Channel, ChannelMember, Message, InAppNotification
from chat.presence_cache import touch_channel_view, touch_dm_view


class RegisterViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_mismatched_passwords_does_not_create_user(self):
        n = User.objects.count()
        r = self.client.post(
            reverse("chat:register"),
            {
                "username": "newu1",
                "email": "newu1@example.com",
                "password1": "verylongpass123",
                "password2": "otherpass456",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.count(), n)
        self.assertContains(r, "Hasła")

    def test_duplicate_email_shows_error_not_logged_in(self):
        User.objects.create_user(
            username="existing", email="dup@example.com", password="x"
        )
        n = User.objects.count()
        r = self.client.post(
            reverse("chat:register"),
            {
                "username": "othername",
                "email": "dup@example.com",
                "password1": "longpassword123",
                "password2": "longpassword123",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(User.objects.count(), n)
        self.assertContains(r, "e-mail")
        self.assertFalse(r.wsgi_request.user.is_authenticated)

    def test_valid_registration_creates_user_and_redirects(self):
        r = self.client.post(
            reverse("chat:register"),
            {
                "username": "brandnew",
                "email": "brandnew@example.com",
                "password1": "longpassword123",
                "password2": "longpassword123",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username="brandnew").exists())


class InAppNotificationTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user(username="na", password="x")
        self.b = User.objects.create_user(username="nb", password="x")
        self.ch = Channel.objects.create(nazwa="c1", opis="", tworca=self.a)
        ChannelMember.objects.create(user=self.a, channel=self.ch)
        ChannelMember.objects.create(user=self.b, channel=self.ch)

    def test_notify_channel_creates_row_for_recipient(self):
        from chat.inbox_notify import notify_channel_message_saved

        msg = Message.objects.create(autor=self.a, channel=self.ch, tresc="hi")
        notify_channel_message_saved(msg)
        self.assertEqual(InAppNotification.objects.filter(user=self.b).count(), 1)
        n = InAppNotification.objects.get(user=self.b)
        self.assertEqual(n.kind, InAppNotification.KIND_CHANNEL)
        self.assertIn("/kanal/", n.url)
        self.assertFalse(n.hidden)

    def test_notify_channel_hidden_when_recipient_views_channel(self):
        from chat.inbox_notify import notify_channel_message_saved

        touch_channel_view(self.b.id, self.ch.id)
        msg = Message.objects.create(autor=self.a, channel=self.ch, tresc="hi")
        notify_channel_message_saved(msg)
        n = InAppNotification.objects.get(user=self.b)
        self.assertTrue(n.hidden)

    def test_notify_dm_hidden_when_recipient_views_conversation(self):
        from chat.inbox_notify import notify_dm_message_saved

        touch_dm_view(self.b.id, self.a.id)
        msg = Message.objects.create(autor=self.a, odbiorca=self.b, tresc="dm")
        notify_dm_message_saved(msg)
        n = InAppNotification.objects.get(user=self.b)
        self.assertEqual(n.kind, InAppNotification.KIND_DM)
        self.assertTrue(n.hidden)

    def test_purge_removes_old_read_notifications(self):
        old = timezone.now() - timedelta(hours=24)
        InAppNotification.objects.create(
            user=self.b,
            kind=InAppNotification.KIND_DM,
            title="t",
            body="b",
            url="/dm/1/",
            read_at=old,
        )
        deleted_count = purge_expired_read_inapp_notifications()
        self.assertGreaterEqual(deleted_count, 1)
        self.assertEqual(InAppNotification.objects.filter(user=self.b).count(), 0)

    def test_purge_removes_old_hidden_notifications(self):
        n = InAppNotification.objects.create(
            user=self.b,
            kind=InAppNotification.KIND_DM,
            title="t",
            body="b",
            url="/dm/1/",
            hidden=True,
        )
        InAppNotification.objects.filter(pk=n.pk).update(
            created_at=timezone.now() - timedelta(hours=24)
        )
        deleted_count = purge_expired_read_inapp_notifications()
        self.assertGreaterEqual(deleted_count, 1)
        self.assertFalse(InAppNotification.objects.filter(pk=n.pk).exists())


class ChannelMediaUploadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.u = User.objects.create_user(username="uimg", password="pw12longenough")
        self.ch = Channel.objects.create(nazwa="ch1", opis="", tworca=self.u)
        ChannelMember.objects.create(user=self.u, channel=self.ch)

    def test_channel_media_upload_returns_echo_with_image_url(self):
        self.client.login(username="uimg", password="pw12longenough")
        # minimal valid GIF (1×1 px)
        gif = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00"
            b"\x02\x02\x04\x01\x00;"
        )
        img = SimpleUploadedFile("a.gif", gif, content_type="image/gif")
        url = reverse("chat:channel_media_upload", kwargs={"channel_id": self.ch.id})
        r = self.client.post(
            url,
            {"tresc": "", "obrazek": img},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data.get("ok"))
        self.assertIn("message_id", data)
        self.assertIn("echo", data)
        self.assertTrue(data["echo"].get("image_url"))
        msg = Message.objects.get(pk=data["message_id"])
        self.assertEqual(msg.channel_id, self.ch.id)

    def test_channel_media_upload_forbidden_non_member(self):
        outsider = User.objects.create_user(username="out", password="pw12longenough")
        self.client.login(username="out", password="pw12longenough")
        img = SimpleUploadedFile("a.png", b"x", content_type="image/png")
        url = reverse("chat:channel_media_upload", kwargs={"channel_id": self.ch.id})
        r = self.client.post(url, {"tresc": "", "obrazek": img})
        self.assertEqual(r.status_code, 403)


class NotificationsSettingsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="n1", password="x")

    def test_notifications_page_requires_login(self):
        r = self.client.get(reverse("chat:notifications_settings"))
        self.assertEqual(r.status_code, 302)

    def test_notifications_page_ok(self):
        self.client.login(username="n1", password="x")
        r = self.client.get(reverse("chat:notifications_settings"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Powiadomienia w aplikacji")


class AccountSuspendedMiddlewareTests(TestCase):
    def test_inactive_user_gets_suspended_page(self):
        u = User.objects.create_user(username="ina", password="x", is_active=False)
        self.client.force_login(u)
        r = self.client.get("/")
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "zablokowane", status_code=403)

    def test_inactive_user_can_logout(self):
        u = User.objects.create_user(username="inb", password="x", is_active=False)
        self.client.force_login(u)
        r = self.client.get(reverse("chat:logout"), follow=False)
        self.assertIn(r.status_code, (301, 302))


class AdminAccountBlockTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(username="adm", password="adm")
        self.admin.profile.role = "admin"
        self.admin.profile.save()
        self.victim = User.objects.create_user(username="vic", password="vicpw")

    def test_login_blocked_message_when_password_correct(self):
        self.victim.is_active = False
        self.victim.save()
        r = self.client.post(
            reverse("chat:login"),
            {"username": "vic", "password": "vicpw"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "zablokowane")
        self.assertFalse(r.wsgi_request.user.is_authenticated)

    def test_login_generic_when_inactive_wrong_password(self):
        self.victim.is_active = False
        self.victim.save()
        r = self.client.post(
            reverse("chat:login"),
            {"username": "vic", "password": "wrong"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Nieprawidłowa nazwa użytkownika lub hasło.")

    def test_admin_can_deactivate_user_via_panel(self):
        self.client.login(username="adm", password="adm")
        r = self.client.post(
            reverse("chat:admin_toggle_user_active", args=[self.victim.pk]),
            {"action": "deactivate"},
        )
        self.assertEqual(r.status_code, 302)
        self.victim.refresh_from_db()
        self.assertFalse(self.victim.is_active)


class ModeratorBlockTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.mod = User.objects.create_user(username="modu", password="modpw")
        self.mod.profile.role = "moderator"
        self.mod.profile.save()
        self.admin = User.objects.create_user(username="adm2", password="admpw")
        self.admin.profile.role = "admin"
        self.admin.profile.save()
        self.regular = User.objects.create_user(username="regu", password="regpw")
        self.other_mod = User.objects.create_user(username="omod", password="ompw")
        self.other_mod.profile.role = "moderator"
        self.other_mod.profile.save()

    def test_moderator_can_deactivate_regular_user(self):
        self.client.login(username="modu", password="modpw")
        r = self.client.post(
            reverse("chat:admin_toggle_user_active", args=[self.regular.pk]),
            {"action": "deactivate", "next": reverse("chat:admin_users")},
        )
        self.assertEqual(r.status_code, 302)
        self.regular.refresh_from_db()
        self.assertFalse(self.regular.is_active)

    def test_moderator_cannot_deactivate_admin(self):
        self.client.login(username="modu", password="modpw")
        r = self.client.post(
            reverse("chat:admin_toggle_user_active", args=[self.admin.pk]),
            {"action": "deactivate"},
        )
        self.assertEqual(r.status_code, 302)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_moderator_cannot_deactivate_other_moderator(self):
        self.client.login(username="modu", password="modpw")
        r = self.client.post(
            reverse("chat:admin_toggle_user_active", args=[self.other_mod.pk]),
            {"action": "deactivate"},
        )
        self.assertEqual(r.status_code, 302)
        self.other_mod.refresh_from_db()
        self.assertTrue(self.other_mod.is_active)

    def test_moderator_can_open_moderation_panel(self):
        self.client.login(username="modu", password="modpw")
        r = self.client.get(reverse("chat:admin_users"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Panel moderacji")

    def test_moderator_cannot_change_role_via_endpoint(self):
        self.client.login(username="modu", password="modpw")
        r = self.client.post(
            reverse("chat:change_role", args=[self.regular.pk]),
            {"role": "moderator"},
        )
        self.assertEqual(r.status_code, 302)
        self.regular.profile.refresh_from_db()
        self.assertEqual(self.regular.profile.role, "user")


class MessagePushPreviewTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user(username="pa", password="x")
        self.b = User.objects.create_user(username="pb", password="x")
        self.ch = Channel.objects.create(nazwa="chan", opis="", tworca=self.a)
        ChannelMember.objects.create(user=self.a, channel=self.ch)

    def test_preview_prefers_text(self):
        m = Message(autor=self.a, channel=self.ch, tresc="  hello  ")
        self.assertEqual(message_push_preview(m), "hello")

    def test_preview_image_only(self):
        img = SimpleUploadedFile("f.jpg", b"\xff\xd8\xff", content_type="image/jpeg")
        m = Message.objects.create(autor=self.a, channel=self.ch, tresc="", obrazek=img)
        self.assertEqual(message_push_preview(m), "Zdjęcie")

    def test_preview_audio_only(self):
        aud = SimpleUploadedFile("a.mp3", b"id3", content_type="audio/mpeg")
        m = Message.objects.create(autor=self.a, channel=self.ch, tresc="", audio=aud)
        self.assertEqual(message_push_preview(m), "Plik audio")

    def test_preview_empty(self):
        m = Message.objects.create(autor=self.a, channel=self.ch, tresc="")
        self.assertEqual(message_push_preview(m), "Nowa wiadomość")


class SearchApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="alice", password="x", email="alice@example.com")
        self.other = User.objects.create_user(username="bob", password="x")
        self.channel = Channel.objects.create(nazwa="ogolny", opis="", tworca=self.user)
        ChannelMember.objects.create(user=self.user, channel=self.channel)

    def test_search_api_requires_login(self):
        r = self.client.get(reverse("chat:search_api"), {"q": "ali"})
        self.assertEqual(r.status_code, 302)

    def test_search_api_returns_users_and_channels(self):
        self.client.login(username="alice", password="x")
        r = self.client.get(reverse("chat:search_api"), {"q": "bob"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data["users"]), 1)
        self.assertEqual(data["users"][0]["username"], "bob")

        r2 = self.client.get(reverse("chat:search_api"), {"q": "ogol"})
        self.assertEqual(r2.status_code, 200)
        d2 = r2.json()
        self.assertTrue(any(c["nazwa"] == "ogolny" for c in d2["channels"]))
        ch = next(c for c in d2["channels"] if c["nazwa"] == "ogolny")
        self.assertTrue(ch["is_member"])

    def test_search_api_excludes_self(self):
        self.client.login(username="alice", password="x")
        r = self.client.get(reverse("chat:search_api"), {"q": "alice"})
        data = r.json()
        self.assertEqual(data["users"], [])
