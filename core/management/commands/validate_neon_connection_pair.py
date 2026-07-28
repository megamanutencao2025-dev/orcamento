import os

from django.core.management.base import BaseCommand, CommandError

from eletrico.database_urls import validate_neon_connection_pair


class Command(BaseCommand):
    help = (
        "Confirma que DATABASE_URL e DIRECT_DATABASE_URL pertencem ao mesmo banco Neon."
    )

    def handle(self, *args, **options):
        runtime_url = os.getenv("DATABASE_URL", "").strip()
        direct_url = os.getenv("DIRECT_DATABASE_URL", "").strip()
        if not runtime_url or not direct_url:
            raise CommandError("Defina DATABASE_URL e DIRECT_DATABASE_URL.")
        try:
            validate_neon_connection_pair(runtime_url, direct_url)
        except ValueError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            self.style.SUCCESS("URLs agrupada e direta do Neon são compatíveis.")
        )
