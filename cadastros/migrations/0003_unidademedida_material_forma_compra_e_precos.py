import unicodedata
from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models
from django.db.models.functions import Lower


UNIDADES_PADRAO = (
    ("Unidade", "UN"),
    ("Peça", "PÇ"),
    ("Metro", "M"),
    ("Metro quadrado", "M²"),
    ("Metro cúbico", "M³"),
    ("Centímetro", "CM"),
    ("Milímetro", "MM"),
    ("Quilograma", "KG"),
    ("Grama", "G"),
    ("Litro", "L"),
    ("Mililitro", "ML"),
    ("Rolo", "RL"),
    ("Pacote", "PCT"),
    ("Caixa", "CX"),
    ("Jogo", "JG"),
    ("Par", "PAR"),
)


ALIASES_POR_SIGLA = {
    "UN": {"UN", "UND", "UNID", "UNIDADE", "UNIDADES", "UNIT"},
    "PÇ": {"PC", "PCS", "PCE", "PECA", "PECAS"},
    "M": {"M", "MT", "MTS", "METRO", "METROS"},
    "M²": {
        "M2",
        "MQ",
        "METROQUADRADO",
        "METROSQUADRADOS",
    },
    "M³": {
        "M3",
        "METROCUBICO",
        "METROSCUBICOS",
    },
    "CM": {"CM", "CENTIMETRO", "CENTIMETROS"},
    "MM": {"MM", "MILIMETRO", "MILIMETROS"},
    "KG": {"KG", "KGS", "QUILO", "QUILOS", "QUILOGRAMA", "QUILOGRAMAS"},
    "G": {"G", "GR", "GRS", "GRAMA", "GRAMAS"},
    "L": {"L", "LT", "LTS", "LITRO", "LITROS"},
    "ML": {"ML", "MILILITRO", "MILILITROS"},
    "RL": {"RL", "RLO", "ROLO", "ROLOS"},
    "PCT": {"PCT", "PCTS", "PCTE", "PACOTE", "PACOTES"},
    "CX": {"CX", "CXS", "CAIXA", "CAIXAS"},
    "JG": {"JG", "JGS", "JOGO", "JOGOS"},
    "PAR": {"PAR", "PARES"},
}


def _chave_alias(valor):
    texto = unicodedata.normalize("NFKD", valor or "")
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )
    return "".join(caractere for caractere in texto.upper() if caractere.isalnum())


MAPA_ALIASES = {
    _chave_alias(alias): sigla
    for sigla, aliases in ALIASES_POR_SIGLA.items()
    for alias in aliases
}


def _encontrar_sem_diferenciar_caixa(unidades, atributo, valor):
    procurado = (valor or "").casefold()
    return next(
        (
            unidade
            for unidade in unidades
            if (getattr(unidade, atributo, "") or "").casefold() == procurado
        ),
        None,
    )


def _semear_e_migrar_unidades(apps, schema_editor):
    UnidadeMedida = apps.get_model("cadastros", "UnidadeMedida")
    Material = apps.get_model("cadastros", "Material")
    banco = schema_editor.connection.alias
    unidades_manager = UnidadeMedida.objects.using(banco)
    materiais_manager = Material.objects.using(banco)
    unidades = list(unidades_manager.all())

    for nome, sigla in UNIDADES_PADRAO:
        unidade = _encontrar_sem_diferenciar_caixa(unidades, "sigla", sigla)
        if unidade is None:
            unidade = _encontrar_sem_diferenciar_caixa(unidades, "nome", nome)
        if unidade is None:
            unidade = unidades_manager.create(
                nome=nome,
                sigla=sigla,
                ativo=True,
            )
            unidades.append(unidade)

    unidades_por_sigla = {
        unidade.sigla.casefold(): unidade
        for unidade in unidades
    }

    for material in materiais_manager.all().iterator():
        valor_legado = " ".join((material.unidade or "").strip().split())
        unidade = None

        if valor_legado:
            unidade = _encontrar_sem_diferenciar_caixa(
                unidades,
                "sigla",
                valor_legado,
            )
            if unidade is None:
                unidade = _encontrar_sem_diferenciar_caixa(
                    unidades,
                    "nome",
                    valor_legado,
                )

        if unidade is None:
            sigla_padrao = MAPA_ALIASES.get(_chave_alias(valor_legado), "UN")
            unidade = unidades_por_sigla[sigla_padrao.casefold()]

        if valor_legado and _chave_alias(valor_legado) not in MAPA_ALIASES:
            sigla_legada = valor_legado.upper()[:30]
            unidade_legada = _encontrar_sem_diferenciar_caixa(
                unidades,
                "sigla",
                sigla_legada,
            )
            if unidade_legada is None:
                unidade_legada = _encontrar_sem_diferenciar_caixa(
                    unidades,
                    "nome",
                    valor_legado,
                )
            if unidade_legada is None:
                unidade_legada = unidades_manager.create(
                    nome=valor_legado[:100],
                    sigla=sigla_legada,
                    ativo=True,
                )
                unidades.append(unidade_legada)
            unidade = unidade_legada

        materiais_manager.filter(pk=material.pk).update(
            forma_compra="unidade",
            preco_caixa=None,
            quantidade_unidades_caixa=None,
            unidade_medida_id=unidade.pk,
        )


def _restaurar_unidades_legadas(apps, schema_editor):
    UnidadeMedida = apps.get_model("cadastros", "UnidadeMedida")
    Material = apps.get_model("cadastros", "Material")
    banco = schema_editor.connection.alias
    unidades_manager = UnidadeMedida.objects.using(banco)
    materiais_manager = Material.objects.using(banco)
    siglas = dict(unidades_manager.values_list("pk", "sigla"))

    for material in materiais_manager.all().iterator():
        sigla = siglas.get(material.unidade_medida_id, "UN")
        materiais_manager.filter(pk=material.pk).update(unidade=sigla[:30])


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0002_categoriamaterial_material_fonte_importacao_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="UnidadeMedida",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("nome", models.CharField(max_length=100)),
                ("sigla", models.CharField(max_length=30)),
            ],
            options={
                "verbose_name": "unidade de medida",
                "verbose_name_plural": "unidades de medida",
                "ordering": ["nome"],
                "constraints": [
                    models.UniqueConstraint(
                        Lower("nome"),
                        name="unidade_medida_nome_unico_ci",
                    ),
                    models.UniqueConstraint(
                        Lower("sigla"),
                        name="unidade_medida_sigla_unica_ci",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="material",
            name="forma_compra",
            field=models.CharField(
                choices=[("unidade", "Unidade"), ("caixa", "Caixa")],
                default="unidade",
                max_length=10,
                verbose_name="forma de compra",
            ),
        ),
        migrations.AddField(
            model_name="material",
            name="preco_caixa",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.00"))
                ],
                verbose_name="preço da caixa",
            ),
        ),
        migrations.AddField(
            model_name="material",
            name="quantidade_unidades_caixa",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name="quantidade de unidades por caixa",
            ),
        ),
        migrations.AddField(
            model_name="material",
            name="unidade_medida",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="materiais",
                to="cadastros.unidademedida",
                verbose_name="unidade de medida",
            ),
        ),
        migrations.RunPython(
            _semear_e_migrar_unidades,
            _restaurar_unidades_legadas,
        ),
        migrations.RemoveField(
            model_name="material",
            name="unidade",
        ),
        migrations.AlterField(
            model_name="material",
            name="unidade_medida",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="materiais",
                to="cadastros.unidademedida",
                verbose_name="unidade de medida",
            ),
        ),
        migrations.AddConstraint(
            model_name="material",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        forma_compra="unidade",
                        preco_caixa__isnull=True,
                        quantidade_unidades_caixa__isnull=True,
                    )
                    | models.Q(
                        forma_compra="caixa",
                        preco_caixa__isnull=False,
                        quantidade_unidades_caixa__gte=1,
                    )
                ),
                name="material_forma_compra_coerente",
            ),
        ),
        migrations.AlterField(
            model_name="material",
            name="preco_unitario",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=12,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0.00"))
                ],
                verbose_name="preço calculado por unidade",
            ),
        ),
    ]
