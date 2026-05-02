from chat.models import InAppNotification


def in_app_notifications(request):
    if not request.user.is_authenticated or not getattr(request.user, "is_active", True):
        return {"in_app_unread_count": 0}
    return {
        "in_app_unread_count": InAppNotification.objects.filter(
            user=request.user, read_at__isnull=True, hidden=False
        ).count(),
    }
