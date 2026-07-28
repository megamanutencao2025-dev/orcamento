from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from cadastros.models import Dificuldade, Servico, TrabalhoAltura

ZERO = Decimal("0.00")
POSITIVO = [MinValueValidator(Decimal("0.01"))]
NAO_NEGATIVO = [MinValueValidator(ZERO)]


class AnaliseProdutividade(models.Model):
    nome = models.CharField(max_length=160)
    data = models.DateField()
    cliente_obra = models.CharField(max_length=200, blank=True)
    valor_total_cobrado = models.DecimalField(
        max_digits=14, decimal_places=2, validators=POSITIVO
    )
    valor_materiais = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO, validators=NAO_NEGATIVO
    )
    valor_deslocamento = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO, validators=NAO_NEGATIVO
    )
    outros_custos = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO, validators=NAO_NEGATIVO
    )
    valor_base_mao_obra = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO
    )
    horas_homem_total = models.DecimalField(
        max_digits=14, decimal_places=3, default=ZERO
    )
    valor_hora_real = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "-id"]
        verbose_name = "análise de produtividade"
        verbose_name_plural = "análises de produtividade"

    def __str__(self):
        return self.nome


class ItemExecutado(models.Model):
    analise = models.ForeignKey(
        AnaliseProdutividade, related_name="itens", on_delete=models.CASCADE
    )
    servico = models.ForeignKey(
        Servico, null=True, blank=True, on_delete=models.SET_NULL
    )
    nome_servico = models.CharField(max_length=160)
    unidade = models.CharField(max_length=30)
    quantidade = models.DecimalField(max_digits=12, decimal_places=3, validators=POSITIVO)
    tempo_horas = models.DecimalField(max_digits=10, decimal_places=3, validators=POSITIVO)
    quantidade_pessoas = models.DecimalField(
        max_digits=8, decimal_places=2, validators=POSITIVO
    )
    dificuldade = models.ForeignKey(
        Dificuldade, null=True, blank=True, on_delete=models.SET_NULL
    )
    altura = models.ForeignKey(
        TrabalhoAltura, null=True, blank=True, on_delete=models.SET_NULL
    )
    horas_homem = models.DecimalField(max_digits=14, decimal_places=3, default=ZERO)
    produtividade = models.DecimalField(max_digits=14, decimal_places=4, default=ZERO)
    tempo_por_unidade = models.DecimalField(
        max_digits=14, decimal_places=4, default=ZERO
    )
    valor_calculado = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    valor_unitario_sugerido = models.DecimalField(
        max_digits=14, decimal_places=2, default=ZERO
    )
    observacoes = models.CharField(max_length=250, blank=True)

    class Meta:
        verbose_name = "item executado"
        verbose_name_plural = "itens executados"
