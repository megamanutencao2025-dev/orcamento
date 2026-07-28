from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower

CENTAVOS = Decimal("0.01")


class AtivoModel(models.Model):
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CategoriaMaterial(AtivoModel):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "categoria de material"
        verbose_name_plural = "categorias de materiais"

    def __str__(self):
        return self.nome

    def clean(self):
        super().clean()
        self.nome = self.nome.strip()
        duplicada = CategoriaMaterial.objects.filter(nome__iexact=self.nome)
        if self.pk:
            duplicada = duplicada.exclude(pk=self.pk)
        if duplicada.exists():
            raise ValidationError(
                {"nome": "Já existe uma categoria com este nome."}
            )


class UnidadeMedida(AtivoModel):
    nome = models.CharField(max_length=100)
    sigla = models.CharField(max_length=30)

    class Meta:
        ordering = ["nome"]
        verbose_name = "unidade de medida"
        verbose_name_plural = "unidades de medida"
        constraints = [
            models.UniqueConstraint(
                Lower("nome"), name="unidade_medida_nome_unico_ci"
            ),
            models.UniqueConstraint(
                Lower("sigla"), name="unidade_medida_sigla_unica_ci"
            ),
        ]

    def __str__(self):
        return f"{self.nome} — {self.sigla}"

    def clean(self):
        super().clean()
        self.nome = self.nome.strip()
        self.sigla = self.sigla.strip().upper()
        erros = {}
        nomes = UnidadeMedida.objects.filter(nome__iexact=self.nome)
        siglas = UnidadeMedida.objects.filter(sigla__iexact=self.sigla)
        if self.pk:
            nomes = nomes.exclude(pk=self.pk)
            siglas = siglas.exclude(pk=self.pk)
        if nomes.exists():
            erros["nome"] = "Já existe uma unidade com este nome."
        if siglas.exists():
            erros["sigla"] = "Já existe uma unidade com esta sigla."
        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        self.nome = self.nome.strip()
        self.sigla = self.sigla.strip().upper()
        super().save(*args, **kwargs)


class Material(AtivoModel):
    class TipoUso(models.TextChoices):
        FORNECIDO = "fornecido", "Material fornecido/cobrado"
        INSUMO = "insumo", "Insumo interno"
        REFERENCIA = "referencia", "Referência para lista do cliente"

    class FormaCompra(models.TextChoices):
        UNIDADE = "unidade", "Unidade"
        CAIXA = "caixa", "Caixa"

    nome = models.CharField(max_length=160)
    unidade_medida = models.ForeignKey(
        UnidadeMedida,
        related_name="materiais",
        on_delete=models.PROTECT,
        verbose_name="unidade de medida",
    )
    forma_compra = models.CharField(
        "forma de compra",
        max_length=10,
        choices=FormaCompra.choices,
        default=FormaCompra.UNIDADE,
    )
    preco_unitario = models.DecimalField(
        "preço calculado por unidade",
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    preco_caixa = models.DecimalField(
        "preço da caixa",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    quantidade_unidades_caixa = models.PositiveIntegerField(
        "quantidade de unidades por caixa",
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    fornecedor = models.CharField(max_length=160, blank=True)
    tipo_uso = models.CharField(max_length=20, choices=TipoUso.choices)
    categoria = models.ForeignKey(
        CategoriaMaterial,
        related_name="materiais",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    imagem_url = models.URLField(max_length=1000, blank=True)
    url_origem = models.URLField(max_length=1000, blank=True)
    fonte_importacao = models.CharField(max_length=40, blank=True)
    importado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "material"
        verbose_name_plural = "materiais"
        constraints = [
            models.CheckConstraint(
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
            )
        ]

    def __str__(self):
        return self.nome

    @property
    def unidade_sigla(self):
        return self.unidade_medida.sigla

    @property
    def preco_compra(self):
        if self.forma_compra == self.FormaCompra.CAIXA:
            return self.preco_caixa
        return self.preco_unitario

    def _normalizar_compra(self, *, exigir_dados):
        if self.forma_compra == self.FormaCompra.UNIDADE:
            self.preco_caixa = None
            self.quantidade_unidades_caixa = None
            return
        if self.forma_compra != self.FormaCompra.CAIXA:
            return
        erros = {}
        if self.preco_caixa is None:
            erros["preco_caixa"] = "Informe o preço total da caixa."
        if not self.quantidade_unidades_caixa:
            erros["quantidade_unidades_caixa"] = (
                "Informe quantas unidades existem na caixa."
            )
        if erros:
            if exigir_dados:
                raise ValidationError(erros)
            return
        self.preco_unitario = (
            self.preco_caixa / Decimal(self.quantidade_unidades_caixa)
        ).quantize(CENTAVOS, rounding=ROUND_HALF_UP)

    def clean(self):
        super().clean()
        self._normalizar_compra(exigir_dados=False)

    def save(self, *args, **kwargs):
        self._normalizar_compra(exigir_dados=True)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.update(
                {
                    "preco_unitario",
                    "preco_caixa",
                    "quantidade_unidades_caixa",
                }
            )
            kwargs["update_fields"] = update_fields
        super().save(*args, **kwargs)


class Servico(AtivoModel):
    nome = models.CharField(max_length=160)
    unidade = models.CharField(max_length=30)
    preco_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    descricao = models.TextField(blank=True)
    ultimo_preco_sugerido = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    ultima_produtividade = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True
    )
    ultimo_tempo_unidade = models.DecimalField(
        max_digits=14, decimal_places=4, null=True, blank=True
    )
    data_ultima_analise = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "serviço"
        verbose_name_plural = "serviços"

    def __str__(self):
        return self.nome


class Veiculo(AtivoModel):
    nome = models.CharField("nome/modelo", max_length=160)
    km_por_litro = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    preco_combustivel = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ["nome"]
        verbose_name = "veículo"
        verbose_name_plural = "veículos"

    def __str__(self):
        return self.nome


class AdicionalBase(AtivoModel):
    nome = models.CharField(max_length=100)
    percentual = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    descricao = models.TextField(blank=True)

    class Meta:
        abstract = True
        ordering = ["percentual", "nome"]

    def __str__(self):
        return f"{self.nome} — {self.percentual}%"


class Dificuldade(AdicionalBase):
    class Meta(AdicionalBase.Meta):
        verbose_name = "dificuldade"
        verbose_name_plural = "dificuldades"


class TrabalhoAltura(AdicionalBase):
    class Meta(AdicionalBase.Meta):
        verbose_name = "trabalho em altura"
        verbose_name_plural = "trabalhos em altura"
