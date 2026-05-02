import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Tworzy lub aktualizuje konto superużytkownika z zmiennych środowiskowych "
        "(ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD). "
        "Bez ADMIN_PASSWORD komenda nic nie robi (kod 0) — wygodne w predeploy."
    )

    def handle(self, *args, **options):
        password = (os.environ.get("ADMIN_PASSWORD") or "").strip()
        if not password:
            self.stderr.write(
                "ensure_admin_user: pominięto (ustaw ADMIN_PASSWORD, aby utworzyć lub zaktualizować admina).\n"
            )
            return

        username = (os.environ.get("ADMIN_USERNAME") or "admin").strip() or "admin"
        email = (os.environ.get("ADMIN_EMAIL") or "").strip()

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        if email:
            user.email = email
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Utworzono superużytkownika „{username}”."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Zaktualizowano superużytkownika „{username}” (hasło i uprawnienia)."))
