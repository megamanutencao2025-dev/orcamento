from datetime import date
from decimal import Decimal

from django.test import TestCase

from .models import AnaliseProdutividade, ItemExecutado
from .services import calcular_analise


class AnaliseProdutividadeTests(TestCase):
    def test_distribui_valor_por_horas_homem(self):
        analise = AnaliseProdutividade.objects.create(
            nome="Obra residencial",
            data=date.today(),
            valor_total_cobrado=Decimal("2000"),
            valor_materiais=Decimal("500"),
            valor_deslocamento=Decimal("100"),
            outros_custos=Decimal("100"),
        )
        item = ItemExecutado.objects.create(
            analise=analise,
            nome_servico="Instalação de luminárias",
            unidade="un",
            quantidade=Decimal("10"),
            tempo_horas=Decimal("5"),
            quantidade_pessoas=Decimal("2"),
        )

        calcular_analise(analise)
        analise.refresh_from_db()
        item.refresh_from_db()

        self.assertEqual(analise.valor_base_mao_obra, Decimal("1300.00"))
        self.assertEqual(analise.horas_homem_total, Decimal("10.000"))
        self.assertEqual(analise.valor_hora_real, Decimal("130.00"))
        self.assertEqual(item.produtividade, Decimal("1.0000"))
        self.assertEqual(item.tempo_por_unidade, Decimal("1.0000"))
        self.assertEqual(item.valor_unitario_sugerido, Decimal("130.00"))
