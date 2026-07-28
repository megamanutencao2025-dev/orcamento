import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Cria uma cópia consistente do SQLite usando a API de backup nativa."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            required=True,
            help="Novo arquivo SQLite que receberá a cópia.",
        )

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError("A origem conectada não é SQLite.")

        source_name = connection.settings_dict["NAME"]
        source_path = Path(source_name).resolve()
        output_path = Path(options["output"]).resolve()
        if not source_path.is_file():
            raise CommandError("O arquivo SQLite de origem não existe.")
        if output_path.exists():
            raise CommandError("O arquivo de backup já existe.")
        if not output_path.parent.is_dir():
            raise CommandError("O diretório de backup não existe.")
        if source_path == output_path:
            raise CommandError("A origem e o backup não podem ser iguais.")

        connection.close()
        source_uri = f"{source_path.as_uri()}?mode=ro"
        try:
            with sqlite3.connect(
                source_uri,
                uri=True,
                timeout=20,
            ) as source_database:
                with sqlite3.connect(output_path, timeout=20) as backup:
                    source_database.backup(backup)
                    integrity = [
                        row[0] for row in backup.execute("PRAGMA integrity_check")
                    ]
                    foreign_keys = list(backup.execute("PRAGMA foreign_key_check"))
            if integrity != ["ok"] or foreign_keys:
                raise CommandError(
                    "A cópia SQLite não passou na validação de integridade."
                )
        except Exception:
            output_path.unlink(missing_ok=True)
            raise

        self.stdout.write(self.style.SUCCESS("Backup SQLite consistente e íntegro."))
