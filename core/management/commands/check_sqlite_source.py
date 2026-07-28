from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Verifica a integridade do SQLite antes da migração para o Neon."

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError(
                "A origem não é SQLite. Remova DATABASE_URL antes de exportar."
            )

        with connection.cursor() as cursor:
            cursor.execute("PRAGMA integrity_check")
            integrity_rows = [row[0] for row in cursor.fetchall()]
            cursor.execute("PRAGMA foreign_key_check")
            foreign_key_rows = cursor.fetchall()

        if integrity_rows != ["ok"]:
            raise CommandError(
                "O SQLite falhou no integrity_check: " + "; ".join(integrity_rows)
            )
        if foreign_key_rows:
            raise CommandError("O SQLite possui violações de chave estrangeira.")

        self.stdout.write(
            self.style.SUCCESS("SQLite íntegro e sem violações de chave estrangeira.")
        )
