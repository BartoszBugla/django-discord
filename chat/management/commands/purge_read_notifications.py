from django.core.management.base import BaseCommand

from chat.inbox_notify import purge_expired_read_inapp_notifications


class Command(BaseCommand):
    help = "Usuwa z bazy przeczytane powiadomienia in-app starsze niż INAPP_NOTIFICATION_READ_RETENTION_HOURS."

    def handle(self, *args, **options):
        n = purge_expired_read_inapp_notifications()
        self.stdout.write(self.style.SUCCESS(f"Usunięto wpisów: {n}"))
