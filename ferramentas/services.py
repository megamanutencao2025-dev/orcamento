from decimal import Decimal

from django.db import transaction

from .models import AnaliseProdutividade

ZERO = Decimal("0.00")


@transaction.atomic
def calcular_analise(analise: AnaliseProdutividade) -> AnaliseProdutividade:
    analise.valor_base_mao_obra = (
        analise.valor_total_cobrado
        - analise.valor_materiais
        - analise.valor_deslocamento
        - analise.outros_custos
    )

    itens = list(analise.itens.all())
    for item in itens:
        item.horas_homem = item.tempo_horas * item.quantidade_pessoas
    analise.horas_homem_total = sum(
        (item.horas_homem for item in itens), start=ZERO
    )
    analise.valor_hora_real = (
        analise.valor_base_mao_obra / analise.horas_homem_total
        if analise.horas_homem_total > ZERO
        else ZERO
    )
    analise.save()

    for item in itens:
        item.produtividade = item.quantidade / item.horas_homem
        item.tempo_por_unidade = item.horas_homem / item.quantidade
        item.valor_calculado = item.horas_homem * analise.valor_hora_real
        item.valor_unitario_sugerido = item.valor_calculado / item.quantidade
        item.save()
    return analise
