from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.contrib.auth import get_user_model
from django.shortcuts import render


class AccountSuspendedMiddleware:
    """
    Konto wylaczone przez administratora (User.is_active=False).
    ModelBackend nie podstawia nieaktywnego uzytkownika do request.user — dodatkowo
    sprawdzamy SESSION_KEY, zeby zlapac sesje sprzed wylaczenia konta.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        suspended = None

        if user is not None and user.is_authenticated and not user.is_active:
            suspended = user
        else:
            uid = request.session.get(SESSION_KEY)
            if uid:
                User = get_user_model()
                try:
                    cand = User.objects.get(pk=uid)
                except User.DoesNotExist:
                    cand = None
                if cand is not None and not cand.is_active:
                    suspended = cand

        if suspended is None:
            return self.get_response(request)

        path = request.path
        static_url = getattr(settings, "STATIC_URL", "/static/") or "/static/"
        media_url = getattr(settings, "MEDIA_URL", "/media/") or "/media/"

        if (
            path.startswith(static_url)
            or path.startswith(media_url)
            or path.startswith("/logout")
            or path.startswith("/login")
            or path.startswith("/register")
        ):
            return self.get_response(request)

        return render(request, "chat/account_suspended.html", status=403)
