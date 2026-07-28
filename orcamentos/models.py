from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from cadastros.models import Dificuldade, Material, Servico, TrabalhoAltura, Veiculo

ZERO = Decimal("0.00")
NAO_NEGATIVO = [MinValueValidator(ZERO)]
POSITIVO = [MinValueValidator(Decimal("0.01"))]


class Orcamento(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        ENVIADO = "enviado", "Enviado"
        APROVADO = "aprovado", "Aprovado"
        RECUSADO = "recusado", "Recusado"

    class MetodoMaoObra(models.TextChoices):
        SERVICOS = "servicos", "Por serviços lançados"
        TEMPO = "tempo", "Por tempo estimado × valor hora"

    class ModoApresentacao(models.TextChoices):
        DETALHADO = "detalhado", "Detalhado"
        PRECO_GLOBAL = "preco_global", "Preço global"

    numero = models.CharField(max_length=30, unique=True, blank=True)
    data = models.DateField(default=timezone.localdate)
    validade = models.DateField()
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.RASCUNHO
    )
    modo_apresentacao = models.CharField(
        "apresentação da proposta",
        max_length=20,
        choices=ModoApresentacao.choices,
        default=ModoApresentacao.DETALHADO,
    )
    cliente_nome = models.CharField("nome do cliente", max_length=160)
    cliente_telefone = models.CharField("telefone do cliente", max_length=30, blank=True)
    endereco_obra = models.CharField(max_length=250, blank=True)

    veiculo = models.ForeignKey(
        Veiculo, null=True, blank=True, on_delete=models.SET_NULL
    )
    distancia_km = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO, validators=NAO_NEGATIVO
    )
    custo_deslocamento = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, validators=NAO_NEGATIVO
    )

    metodo_mao_obra = models.CharField(
        max_length=15,
        choices=MetodoMaoObra.choices,
        default=MetodoMaoObra.SERVICOS,
    )
    tempo_estimado_horas = models.DecimalField(
        max_digits=10, decimal_places=2, default=ZERO, validators=NAO_NEGATIVO
    )
    valor_hora = models.DecimalField(
        max_digits=12, decimal_places=2, default=ZERO, validators=NAO_NEGATIVO
    )
    percentual_ferramentas = models.DecimalField(
        max_digits=6, decimal_places=2, default=ZERO, validators=NAO_NEGATIVO
    )
    percentual_empresa = models.DecimalField(
        max_digits=6, decimal_places=2, default=ZERO, validators=NAO_NEGATIVO
    )
    percentual_lucro = models.DecimalField(
        max_digits=6, decimal_places=2, default=ZERO, validators=NAO_NEGATIVO
    )
    desconto = models.DecimalField(
        "desconto comercial",
        max_digits=14,
        decimal_places=2,
        default=ZERO,
        validators=NAO_NEGATIVO,
    )
    observacoes_internas = models.TextField(blank=True)
    observacoes_cliente = models.TextField(blank=True)

    subtotal_materiais = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    subtotal_insumos = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    subtotal_servicos_base = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO
    )
    total_dificuldade = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    total_altura = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    subtotal_servicos_final = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO
    )
    outros_custos_total = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    custos_diretos = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    valor_mao_obra = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    reserva_ferramentas = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    subtotal_operacional = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    reserva_empresa = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    subtotal_antes_lucro = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    lucro_liquido = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    total_final = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "-id"]
        verbose_name = "orçamento"
        verbose_name_plural = "orçamentos"

    def __str__(self):
        return f"{self.numero} — {self.cliente_nome}"

    def _gerar_numero(self):
        ano = (self.data or timezone.localdate()).year
        prefixo = f"ORC-{ano}-"
        maior_sequencia = 0
        numeros = Orcamento.objects.filter(
            numero__startswith=prefixo
        ).values_list("numero", flat=True)
        for numero in numeros:
            try:
                maior_sequencia = max(
                    maior_sequencia, int(numero.removeprefix(prefixo))
                )
            except ValueError:
                continue
        return f"{prefixo}{maior_sequencia + 1:04d}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._gerar_numero()
        super().save(*args, **kwargs)


class ItemFinanceiroBase(models.Model):
    descricao = models.CharField(max_length=180)
    unidade = models.CharField(max_length=30)
    quantidade = models.DecimalField(
        max_digits=12, decimal_places=3, validators=POSITIVO
    )
    preco_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, validators=NAO_NEGATIVO
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.subtotal = (self.quantidade * self.preco_unitario).quantize(
            Decimal("0.01")
        )
        super().save(*args, **kwargs)


class MaterialFornecido(ItemFinanceiroBase):
    orcamento = models.ForeignKey(
        Orcamento, related_name="materiais_fornecidos", on_delete=models.CASCADE
    )
    material = models.ForeignKey(
        Material, null=True, blank=True, on_delete=models.SET_NULL
    )
    fornecedor = models.CharField(max_length=160, blank=True)

    class Meta:
        verbose_name = "material fornecido"
        verbose_name_plural = "materiais fornecidos"


class MaterialCliente(models.Model):
    orcamento = models.ForeignKey(
        Orcamento, related_name="materiais_cliente", on_delete=models.CASCADE
    )
    material_referencia = models.ForeignKey(
        Material, null=True, blank=True, on_delete=models.SET_NULL
    )
    descricao = models.CharField(max_length=180)
    quantidade = models.DecimalField(
        max_digits=12, decimal_places=3, validators=POSITIVO
    )
    unidade = models.CharField(max_length=30)
    observacao = models.CharField(max_length=250, blank=True)

    class Meta:
        verbose_name = "material para o cliente"
        verbose_name_plural = "materiais para o cliente"


class InsumoInterno(ItemFinanceiroBase):
    orcamento = models.ForeignKey(
        Orcamento, related_name="insumos_internos", on_delete=models.CASCADE
    )
    material = models.ForeignKey(
        Material, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name = "insumo interno"
        verbose_name_plural = "insumos internos"


class ItemServico(models.Model):
    orcamento = models.ForeignKey(
        Orcamento, related_name="servicos", on_delete=models.CASCADE
    )
    servico = models.ForeignKey(
        Servico, null=True, blank=True, on_delete=models.SET_NULL
    )
    descricao = models.CharField(max_length=180)
    unidade = models.CharField(max_length=30)
    quantidade = models.DecimalField(
        max_digits=12, decimal_places=3, validators=POSITIVO
    )
    preco_unitario = models.DecimalField(
        max_digits=12, decimal_places=2, validators=NAO_NEGATIVO
    )
    dificuldade = models.ForeignKey(
        Dificuldade, null=True, blank=True, on_delete=models.SET_NULL
    )
    altura = models.ForeignKey(
        TrabalhoAltura, null=True, blank=True, on_delete=models.SET_NULL
    )
    subtotal_base = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    valor_dificuldade = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    valor_altura = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    subtotal_final = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)

    def save(self, *args, **kwargs):
        self.subtotal_base = (self.quantidade * self.preco_unitario).quantize(
            Decimal("0.01")
        )
        dificuldade = self.dificuldade.percentual if self.dificuldade else ZERO
        altura = self.altura.percentual if self.altura else ZERO
        self.valor_dificuldade = (
            self.subtotal_base * dificuldade / Decimal("100")
        ).quantize(Decimal("0.01"))
        self.valor_altura = (
            self.subtotal_base * altura / Decimal("100")
        ).quantize(Decimal("0.01"))
        self.subtotal_final = (
            self.subtotal_base + self.valor_dificuldade + self.valor_altura
        )
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "serviço do orçamento"
        verbose_name_plural = "serviços do orçamento"


class OutroCusto(models.Model):
    orcamento = models.ForeignKey(
        Orcamento, related_name="outros_custos", on_delete=models.CASCADE
    )
    descricao = models.CharField(max_length=180)
    valor = models.DecimalField(
        max_digits=12, decimal_places=2, validators=NAO_NEGATIVO
    )

    class Meta:
        verbose_name = "outro custo"
        verbose_name_plural = "outros custos"
