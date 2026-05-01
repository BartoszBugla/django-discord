"""Middleware ASGI dla WebSocket (Channels) — spojne z HTTP AccountSuspendedMiddleware."""


class InactiveUserWebSocketMiddleware:
    """
    Zamyka polaczenie WebSocket, gdy uzytkownik w sesji ma User.is_active=False.
    AuthMiddlewareStack musi byc na zewnatrz, zeby scope['user'] byl juz ustawiony.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            user = scope.get("user")
            if (
                user is not None
                and getattr(user, "is_authenticated", False)
                and not getattr(user, "is_active", True)
            ):
                await send(
                    {
                        "type": "websocket.close",
                        "code": 4003,
                        "reason": b"Account disabled",
                    }
                )
                return
        return await self.inner(scope, receive, send)
