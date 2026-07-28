import json
from pathlib import Path

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


MODEL_LABELS = (
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

QUOTE_MONEY_FIELDS = (
    "subtotal_materiais",
    "subtotal_insumos",
    "subtotal_servicos_base",
    "total_dificuldade",
    "total_altura",
    "subtotal_servicos_final",
    "custo_deslocamento",
    "outros_custos_total",
    "custos_diretos",
    "valor_mao_obra",
    "reserva_ferramentas",
    "subtotal_operacional",
    "reserva_empresa",
    "subtotal_antes_lucro",
    "lucro_liquido",
    "desconto",
    "total_final",
)


class Command(BaseCommand):
    help = (
        "Gera um retrato determinístico para comparar os dados antes e "
        "depois da migração."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            help="Arquivo JSON de saída. Se omitido, escreve no terminal.",
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        quote_model = apps.get_model("orcamentos.Orcamento")
        snapshot = {
            "counts": {
                label: apps.get_model(label).objects.count() for label in MODEL_LABELS
            },
            "users": [
                {
                    "username": user.username,
                    "active": user.is_active,
                    "staff": user.is_staff,
                    "superuser": user.is_superuser,
                    "usable_password": user.has_usable_password(),
                }
                for user in user_model.objects.order_by("username")
            ],
            "quotes": [
                {
                    "numero": quote.numero,
                    **{
                        field: str(getattr(quote, field))
                        for field in QUOTE_MONEY_FIELDS
                    },
                }
                for quote in quote_model.objects.order_by("numero")
            ],
        }
        content = json.dumps(
            snapshot,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )

        output = options.get("output")
        if output:
            output_path = Path(output).resolve()
            output_path.write_text(content, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS("Retrato de dados gerado."))
            return
        self.stdout.write(content)
