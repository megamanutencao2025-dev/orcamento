from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


EXPECTED_UNITS = (
    (1, "Unidade", "UN"),
    (2, "Peça", "PÇ"),
    (3, "Metro", "M"),
    (4, "Metro quadrado", "M²"),
    (5, "Metro cúbico", "M³"),
    (6, "Centímetro", "CM"),
    (7, "Milímetro", "MM"),
    (8, "Quilograma", "KG"),
    (9, "Grama", "G"),
    (10, "Litro", "L"),
    (11, "Mililitro", "ML"),
    (12, "Rolo", "RL"),
    (13, "Pacote", "PCT"),
    (14, "Caixa", "CX"),
    (15, "Jogo", "JG"),
    (16, "Par", "PAR"),
)

EMPTY_TARGET_MODELS = (
    "auth.Group",
    "auth.User",
    "admin.LogEntry",
    "sessions.Session",
    "core.Configuracao",
    "cadastros.CategoriaMaterial",
    "cadastros.Material",
    "cadastros.Servico",
    "cadastros.Veiculo",
    "cadastros.Dificuldade",
    "cadastros.TrabalhoAltura",
    "orcamentos.Orcamento",
    "orcamentos.MaterialFornecido",
    "orcamentos.MaterialCliente",
    "orcamentos.InsumoInterno",
    "orcamentos.ItemServico",
    "orcamentos.OutroCusto",
    "ferramentas.AnaliseProdutividade",
    "ferramentas.ItemExecutado",
)


class Command(BaseCommand):
    help = "Confirma que o Neon está vazio e seguro para receber a fixture local."

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-non-postgres",
            action="store_true",
            help="Permite outro banco somente para testes automatizados.",
        )

    def handle(self, *args, **options):
        allow_non_postgres = options["allow_non_postgres"]
        if connection.vendor != "postgresql" and not allow_non_postgres:
            raise CommandError("O destino não é PostgreSQL. Use a URL direta do Neon.")

        host = str(connection.settings_dict.get("HOST", "")).lower()
        if connection.vendor == "postgresql" and not host.endswith(".neon.tech"):
            raise CommandError(
                "O PostgreSQL informado não pertence ao Neon (*.neon.tech)."
            )

        occupied = []
        for model_label in EMPTY_TARGET_MODELS:
            model = apps.get_model(model_label)
            count = model.objects.count()
            if count:
                occupied.append(f"{model_label}={count}")
        if occupied:
            details = ", ".join(occupied)
            raise CommandError(
                "O banco de destino já contém dados e não será alterado: "
                f"{details}. Crie um projeto/branch vazio no Neon."
            )

        unit_model = apps.get_model("cadastros.UnidadeMedida")
        units = tuple(
            unit_model.objects.order_by("pk").values_list(
                "pk",
                "nome",
                "sigla",
            )
        )
        if units != EXPECTED_UNITS:
            raise CommandError(
                "As unidades iniciais do destino não correspondem às 16 "
                "unidades criadas pelas migrations. Use um banco Neon vazio."
            )

        self.stdout.write(
            self.style.SUCCESS("Destino Neon vazio e compatível com a importação.")
        )
