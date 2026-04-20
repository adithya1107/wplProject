import time
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError

class Command(BaseCommand):
    help = 'Waits for database to be available'

    def handle(self, *args, **options):
        self.stdout.write('Waiting for database...')
        attempts = 0
        while attempts < 30:
            try:
                conn = connections['default']
                conn.ensure_connection()
                self.stdout.write(self.style.SUCCESS('Database available!'))
                return
            except OperationalError:
                attempts += 1
                self.stdout.write(f'Attempt {attempts}/30 - retrying in 2s...')
                time.sleep(2)
        raise SystemExit(1)