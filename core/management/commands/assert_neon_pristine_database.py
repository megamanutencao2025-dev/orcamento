from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = (
        "Confirma, antes das migrations, que o schema public do Neon "
        "não possui tabelas."
    )

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("O destino não é PostgreSQL. Use a URL direta do Neon.")

        host = str(connection.settings_dict.get("HOST", "")).lower()
        if not host.endswith(".neon.tech") or "-pooler" in host:
            raise CommandError("Use uma URL direta válida do Neon, sem -pooler.")

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename
                FROM pg_catalog.pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
                """
            )
            tables = [row[0] for row in cursor.fetchall()]

        if tables:
            raise CommandError(
                "O schema public do Neon já contém tabelas e não será "
                "alterado. Crie um projeto/branch vazio."
            )

        self.stdout.write(
            self.style.SUCCESS("Schema public do Neon vazio e pronto para migrations.")
        )
