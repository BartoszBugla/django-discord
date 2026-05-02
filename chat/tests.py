from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from chat.inbox_notify import message_push_preview
from chat.models import Channel, ChannelMember, Message


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
