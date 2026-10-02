def notifications(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {"unread_notifications": user.notifications.filter(read_at__isnull=True).count()}
