from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Configuracao(models.Model):
    """Preferências globais do eletricista e padrões de novos orçamentos."""

    nome_eletricista = models.CharField(max_length=160, blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    cidade = models.CharField(max_length=120, blank=True)
    validade_padrao_dias = models.PositiveIntegerField(default=15)
    valor_hora_padrao = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    percentual_ferramentas = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("5.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    percentual_empresa = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    percentual_lucro = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("20.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    mostrar_deslocamento_proposta = models.BooleanField(default=False)
    observacao_cliente_padrao = models.TextField(blank=True)
    observacao_interna_padrao = models.TextField(blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuração"
        verbose_name_plural = "configurações"

    def __str__(self):
        return "Configurações do aplicativo"

    @classmethod
    def carregar(cls):
        configuracao, _ = cls.objects.get_or_create(pk=1)
        return configuracao

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
