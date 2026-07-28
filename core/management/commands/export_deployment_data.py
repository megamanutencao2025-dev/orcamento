from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


FIXTURE_MODELS = (
    "auth.Group",
    "auth.User",
    "core.Configuracao",
    "cadastros.CategoriaMaterial",
    "cadastros.UnidadeMedida",
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
    help = "Exporta somente os dados portáveis da aplicação em JSON UTF-8."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            required=True,
            help="Caminho do arquivo JSON que será criado.",
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"]).resolve()
        if not output_path.parent.is_dir():
            raise CommandError("O diretório de saída não existe.")

        with output_path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as stream:
            call_command(
                "dumpdata",
                *FIXTURE_MODELS,
                natural_foreign=True,
                natural_primary=True,
                indent=2,
                stdout=stream,
                verbosity=0,
            )

        self.stdout.write(self.style.SUCCESS("Dados exportados em JSON UTF-8."))
