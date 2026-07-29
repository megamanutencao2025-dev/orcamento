import json
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from cadastros.models import (
    Dificuldade,
    Material,
    Servico,
    TrabalhoAltura,
    UnidadeMedida,
    Veiculo,
)
from core.models import Configuracao

from .composicao_comercial import (
    ComponentePendente,
    ComposicaoComercialInvalida,
    LinhaComercial,
    montar_composicao_comercial,
    validar_fechamento,
)
from .documentos import gerar_proposta_pdf, montar_dados_proposta
from .models import (
    ItemServico,
    MaterialCliente,
    MaterialFornecido,
    Orcamento,
    OutroCusto,
)
from .services import calcular_orcamento


class CalculoOrcamentoTests(TestCase):
    def test_calcula_fluxo_financeiro_completo(self):
        veiculo = Veiculo.objects.create(
            nome="Utilitário",
            km_por_litro=Decimal("10"),
            preco_combustivel=Decimal("6"),
        )
        dificuldade = Dificuldade.objects.create(nome="Média", percentual=10)
        altura = TrabalhoAltura.objects.create(nome="Escada", percentual=20)
        orcamento = Orcamento.objects.create(
            validade=date.today() + timedelta(days=15),
            cliente_nome="Cliente teste",
            veiculo=veiculo,
            distancia_km=Decimal("100"),
            percentual_ferramentas=Decimal("10"),
            percentual_empresa=Decimal("10"),
            percentual_lucro=Decimal("20"),
        )
        ItemServico.objects.create(
            orcamento=orcamento,
            descricao="Instalação",
            unidade="un",
            quantidade=Decimal("2"),
            preco_unitario=Decimal("100"),
            dificuldade=dificuldade,
            altura=altura,
        )
        OutroCusto.objects.create(
            orcamento=orcamento, descricao="Estacionamento", valor=Decimal("20")
        )

        calcular_orcamento(orcamento)
        orcamento.refresh_from_db()

        self.assertEqual(orcamento.subtotal_servicos_final, Decimal("260.00"))
        self.assertEqual(orcamento.custo_deslocamento, Decimal("60.00"))
        self.assertEqual(orcamento.valor_mao_obra, Decimal("260.00"))
        self.assertEqual(orcamento.custos_diretos, Decimal("80.00"))
        self.assertEqual(orcamento.reserva_ferramentas, Decimal("26.00"))
        self.assertEqual(orcamento.reserva_empresa, Decimal("36.60"))
        self.assertEqual(orcamento.lucro_liquido, Decimal("80.52"))
        self.assertEqual(orcamento.total_final, Decimal("483.12"))


class ComposicaoComercialTests(TestCase):
    def _orcamento(self, **valores):
        dados = {
            "validade": date.today() + timedelta(days=15),
            "cliente_nome": "Cliente teste",
        }
        dados.update(valores)
        return Orcamento.objects.create(**dados)

    @staticmethod
    def _valores_por_codigo(composicao):
        return {
            linha.codigo: linha.valor
            for linha in composicao.linhas
        }

    def test_os_002_fecha_em_630_83_preservando_decimal_e_total(self):
        orcamento = self._orcamento(
            numero="OS-002",
            subtotal_materiais=Decimal("99.90"),
            valor_mao_obra=Decimal("360.00"),
            reserva_ferramentas=Decimal("18.00"),
            reserva_empresa=Decimal("47.79"),
            lucro_liquido=Decimal("105.14"),
            total_final=Decimal("630.83"),
        )

        composicao = montar_composicao_comercial(
            orcamento,
            mostrar_deslocamento=False,
        )

        self.assertEqual(composicao.total_final, Decimal("630.83"))
        self.assertEqual(composicao.total_apresentado, Decimal("630.83"))
        valores = self._valores_por_codigo(composicao)
        self.assertEqual(valores["servicos"], Decimal("530.93"))
        self.assertEqual(valores["materiais"], Decimal("99.90"))
        self.assertEqual(
            sum(
                (linha.valor for linha in composicao.linhas),
                Decimal("0.00"),
            ),
            Decimal("630.83"),
        )
        self.assertTrue(
            all(
                isinstance(linha.valor, Decimal)
                for linha in composicao.linhas
            )
        )
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.total_final, Decimal("630.83"))

    def test_componentes_de_execucao_ficam_em_mao_de_obra_e_servicos(self):
        orcamento = self._orcamento(
            subtotal_materiais=Decimal("100.00"),
            valor_mao_obra=Decimal("100.00"),
            subtotal_insumos=Decimal("20.00"),
            outros_custos_total=Decimal("5.00"),
            reserva_ferramentas=Decimal("10.00"),
            total_final=Decimal("235.00"),
        )

        composicao = montar_composicao_comercial(
            orcamento,
            mostrar_deslocamento=False,
        )

        valores = self._valores_por_codigo(composicao)
        self.assertEqual(valores["materiais"], Decimal("100.00"))
        self.assertEqual(valores["servicos"], Decimal("135.00"))
        self.assertEqual(composicao.total_apresentado, Decimal("235.00"))

    def test_custo_geral_e_embutido_somente_em_servicos(self):
        orcamento = self._orcamento(
            subtotal_materiais=Decimal("100.00"),
            valor_mao_obra=Decimal("300.00"),
            reserva_empresa=Decimal("40.00"),
            total_final=Decimal("440.00"),
        )

        composicao = montar_composicao_comercial(
            orcamento,
            mostrar_deslocamento=False,
        )

        valores = self._valores_por_codigo(composicao)
        self.assertEqual(valores["materiais"], Decimal("100.00"))
        self.assertEqual(valores["servicos"], Decimal("340.00"))
        self.assertEqual(composicao.total_apresentado, Decimal("440.00"))

    def test_ultimo_item_absorve_diferenca_de_arredondamento(self):
        orcamento = self._orcamento(
            subtotal_materiais=Decimal("100.00"),
            valor_mao_obra=Decimal("200.00"),
            reserva_empresa=Decimal("0.01"),
            total_final=Decimal("300.01"),
        )

        composicao = montar_composicao_comercial(
            orcamento,
            mostrar_deslocamento=False,
        )

        valores = self._valores_por_codigo(composicao)
        self.assertEqual(valores["materiais"], Decimal("100.00"))
        self.assertEqual(valores["servicos"], Decimal("200.01"))
        self.assertEqual(composicao.total_apresentado, Decimal("300.01"))

    def test_desconto_e_exibido_como_linha_negativa_e_subtraido_do_total(self):
        orcamento = self._orcamento(
            subtotal_materiais=Decimal("100.00"),
            valor_mao_obra=Decimal("200.00"),
            desconto=Decimal("20.00"),
            total_final=Decimal("280.00"),
        )

        composicao = montar_composicao_comercial(
            orcamento,
            mostrar_deslocamento=False,
        )

        valores = self._valores_por_codigo(composicao)
        self.assertEqual(valores["materiais"], Decimal("100.00"))
        self.assertEqual(valores["servicos"], Decimal("200.00"))
        self.assertEqual(valores["desconto"], Decimal("-20.00"))
        self.assertEqual(composicao.total_apresentado, Decimal("280.00"))

    def test_bloqueia_desconto_maior_que_o_valor_bruto(self):
        orcamento = self._orcamento(
            subtotal_materiais=Decimal("10.00"),
            desconto=Decimal("20.00"),
            total_final=Decimal("-10.00"),
        )

        with self.assertRaises(ComposicaoComercialInvalida) as contexto:
            montar_composicao_comercial(
                orcamento,
                mostrar_deslocamento=False,
            )

        erro = contexto.exception
        self.assertEqual(erro.diferenca_absoluta, Decimal("10.00"))
        self.assertIn("desconto maior", erro.messages[0])
        self.assertEqual(
            erro.componentes_pendentes[0].valor,
            Decimal("10.00"),
        )

    def test_deslocamento_visivel_ou_incorporado_nao_e_contado_duas_vezes(self):
        orcamento = self._orcamento(
            subtotal_materiais=Decimal("100.00"),
            valor_mao_obra=Decimal("200.00"),
            custo_deslocamento=Decimal("30.00"),
            total_final=Decimal("330.00"),
        )

        composicao_visivel = montar_composicao_comercial(
            orcamento,
            mostrar_deslocamento=True,
        )
        composicao_incorporada = montar_composicao_comercial(
            orcamento,
            mostrar_deslocamento=False,
        )

        valores_visiveis = self._valores_por_codigo(composicao_visivel)
        self.assertEqual(valores_visiveis["materiais"], Decimal("100.00"))
        self.assertEqual(valores_visiveis["servicos"], Decimal("200.00"))
        self.assertEqual(valores_visiveis["deslocamento"], Decimal("30.00"))
        self.assertEqual(
            composicao_visivel.total_apresentado,
            Decimal("330.00"),
        )

        valores_incorporados = self._valores_por_codigo(
            composicao_incorporada
        )
        self.assertNotIn("deslocamento", valores_incorporados)
        self.assertEqual(
            valores_incorporados["servicos"],
            Decimal("230.00"),
        )
        self.assertEqual(
            composicao_incorporada.total_apresentado,
            Decimal("330.00"),
        )

    def test_validador_informa_diferenca_e_componentes_pendentes(self):
        linhas = (
            LinhaComercial(
                "servicos",
                "Mão de obra e serviços",
                Decimal("360.00"),
            ),
            LinhaComercial(
                "materiais",
                "Materiais fornecidos",
                Decimal("99.90"),
            ),
        )
        pendentes = (
            ComponentePendente(
                "Custos e margens ainda não distribuídos",
                Decimal("170.93"),
            ),
        )

        with self.assertRaises(ComposicaoComercialInvalida) as contexto:
            validar_fechamento(
                linhas,
                Decimal("630.83"),
                componentes_pendentes=pendentes,
            )

        erro = contexto.exception
        self.assertEqual(erro.total_apresentado, Decimal("459.90"))
        self.assertEqual(erro.total_final, Decimal("630.83"))
        self.assertEqual(erro.diferenca, Decimal("170.93"))
        self.assertEqual(erro.componentes_pendentes, pendentes)

    def test_gerador_direto_recusa_dados_cuja_composicao_nao_fecha(self):
        orcamento = self._orcamento(
            subtotal_materiais=Decimal("99.90"),
            valor_mao_obra=Decimal("360.00"),
            reserva_empresa=Decimal("70.93"),
            lucro_liquido=Decimal("100.00"),
            total_final=Decimal("630.83"),
        )
        dados_validos = montar_dados_proposta(
            orcamento,
            Configuracao.carregar(),
        )
        dados_invalidos = replace(
            dados_validos,
            linhas_valores=(
                LinhaComercial(
                    "servicos",
                    "Mão de obra e serviços",
                    Decimal("459.90"),
                ),
            ),
        )

        with self.assertRaises(ComposicaoComercialInvalida) as contexto:
            gerar_proposta_pdf(dados_invalidos)

        self.assertEqual(
            contexto.exception.diferenca,
            Decimal("170.93"),
        )

    def test_preco_global_mostra_total_e_materiais_inclusos(self):
        orcamento = self._orcamento(
            modo_apresentacao=Orcamento.ModoApresentacao.PRECO_GLOBAL,
            subtotal_materiais=Decimal("99.90"),
            valor_mao_obra=Decimal("530.93"),
            reserva_empresa=Decimal("0.00"),
            lucro_liquido=Decimal("0.00"),
            total_final=Decimal("630.83"),
            observacoes_internas="Lucro e reservas confidenciais",
        )
        MaterialFornecido.objects.create(
            orcamento=orcamento,
            descricao="Plafon LED Denver",
            unidade="UN",
            quantidade=Decimal("1"),
            preco_unitario=Decimal("99.90"),
        )
        ItemServico.objects.create(
            orcamento=orcamento,
            descricao="Passar fios até 6 mm",
            unidade="M",
            quantidade=Decimal("60"),
            preco_unitario=Decimal("6.00"),
        )

        dados = montar_dados_proposta(
            orcamento,
            Configuracao.carregar(),
        )

        self.assertEqual(
            dados.modo_apresentacao,
            Orcamento.ModoApresentacao.PRECO_GLOBAL,
        )
        self.assertEqual(len(dados.linhas_valores), 1)
        self.assertEqual(dados.linhas_valores[0].codigo, "preco_global")
        self.assertEqual(dados.linhas_valores[0].valor, Decimal("630.83"))
        self.assertEqual(dados.total, Decimal("630.83"))
        self.assertEqual(
            [item.descricao for item in dados.materiais_inclusos],
            ["Plafon LED Denver"],
        )
        self.assertEqual(
            [item.descricao for item in dados.servicos],
            ["Passar fios até 6 mm"],
        )
        self.assertFalse(hasattr(dados, "lucro_liquido"))
        self.assertFalse(hasattr(dados, "reserva_empresa"))
        self.assertFalse(hasattr(dados, "observacoes_internas"))
        self.assertTrue(gerar_proposta_pdf(dados).startswith(b"%PDF"))

    def test_material_para_cliente_comprar_fica_fora_do_total(self):
        orcamento = self._orcamento(
            subtotal_materiais=Decimal("100.00"),
            valor_mao_obra=Decimal("200.00"),
            total_final=Decimal("300.00"),
        )
        configuracao = Configuracao.carregar()
        dados_antes = montar_dados_proposta(orcamento, configuracao)
        MaterialCliente.objects.create(
            orcamento=orcamento,
            descricao="Cabo flexível 2,5 mm²",
            quantidade=Decimal("1000"),
            unidade="M",
            observacao="Compra direta pelo cliente",
        )

        dados_depois = montar_dados_proposta(orcamento, configuracao)

        self.assertEqual(dados_depois.linhas_valores, dados_antes.linhas_valores)
        self.assertEqual(dados_depois.total, Decimal("300.00"))
        self.assertEqual(
            [item.descricao for item in dados_depois.materiais_compra],
            ["Cabo flexível 2,5 mm²"],
        )
        self.assertEqual(
            sum(
                (linha.valor for linha in dados_depois.linhas_valores),
                Decimal("0.00"),
            ),
            Decimal("300.00"),
        )


class OrcamentoViewsTests(TestCase):
    def setUp(self):
        self.unidade, _ = UnidadeMedida.objects.get_or_create(
            sigla="UN",
            defaults={"nome": "Unidade"},
        )

    def _dados_formulario(
        self,
        *,
        cliente_nome,
        itens,
        numero="",
        modo_apresentacao=Orcamento.ModoApresentacao.DETALHADO,
    ):
        return {
            "numero": numero,
            "data": date.today().isoformat(),
            "validade": (date.today() + timedelta(days=15)).isoformat(),
            "status": Orcamento.Status.RASCUNHO,
            "modo_apresentacao": modo_apresentacao,
            "cliente_nome": cliente_nome,
            "cliente_telefone": "",
            "endereco_obra": "",
            "veiculo": "",
            "distancia_km": "0",
            "metodo_mao_obra": Orcamento.MetodoMaoObra.SERVICOS,
            "tempo_estimado_horas": "0",
            "valor_hora": "0",
            "percentual_ferramentas": "0",
            "percentual_empresa": "0",
            "percentual_lucro": "0",
            "desconto": "0",
            "observacoes_internas": "",
            "observacoes_cliente": "",
            "itens_json": json.dumps(itens),
        }

    def test_dashboard_e_lista_abrem(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/orcamentos/").status_code, 200)

    def test_lista_exibe_acao_excluir_e_post_remove_orcamento(self):
        orcamento = Orcamento.objects.create(
            validade=date.today() + timedelta(days=15),
            cliente_nome="Cliente para exclusão",
        )
        MaterialFornecido.objects.create(
            orcamento=orcamento,
            descricao="Cabo",
            unidade="m",
            quantidade=Decimal("10"),
            preco_unitario=Decimal("5"),
        )

        lista = self.client.get("/orcamentos/")
        self.assertContains(lista, "Excluir")
        self.assertContains(lista, f"/orcamentos/{orcamento.pk}/excluir/")

        resposta = self.client.post(f"/orcamentos/{orcamento.pk}/excluir/")
        self.assertRedirects(resposta, "/orcamentos/")
        self.assertFalse(Orcamento.objects.filter(pk=orcamento.pk).exists())
        self.assertFalse(
            MaterialFornecido.objects.filter(orcamento_id=orcamento.pk).exists()
        )

    def test_excluir_exige_post(self):
        orcamento = Orcamento.objects.create(
            validade=date.today() + timedelta(days=15),
            cliente_nome="Cliente protegido",
        )

        resposta = self.client.get(f"/orcamentos/{orcamento.pk}/excluir/")
        self.assertEqual(resposta.status_code, 405)
        self.assertTrue(Orcamento.objects.filter(pk=orcamento.pk).exists())

    def test_numero_e_gerado_em_sequencia_e_nao_e_editavel(self):
        primeiro = Orcamento.objects.create(
            validade=date.today() + timedelta(days=15),
            cliente_nome="Primeiro cliente",
        )
        segundo = Orcamento.objects.create(
            validade=date.today() + timedelta(days=15),
            cliente_nome="Segundo cliente",
        )

        ano = date.today().year
        self.assertEqual(primeiro.numero, f"ORC-{ano}-0001")
        self.assertEqual(segundo.numero, f"ORC-{ano}-0002")

        resposta = self.client.get("/orcamentos/novo/")
        self.assertContains(resposta, "Gerado ao salvar")
        self.assertNotContains(resposta, 'name="numero"')

    def test_novo_orcamento_preenche_datas_com_a_data_local_em_iso(self):
        data_local = date(2031, 4, 5)

        with patch(
            "orcamentos.views.timezone.localdate",
            return_value=data_local,
        ):
            resposta = self.client.get("/orcamentos/novo/")

        self.assertContains(resposta, 'value="2031-04-05"')
        self.assertContains(resposta, 'value="2031-04-20"')
        self.assertNotContains(resposta, 'value="05/04/2031"')

    def test_construtor_tem_secoes_recolhiveis_e_tabelas_de_itens(self):
        resposta = self.client.get("/orcamentos/novo/")

        self.assertContains(
            resposta, '<details class="builder-section"', count=8
        )
        self.assertContains(
            resposta, '<details class="builder-section builder-summary"'
        )
        self.assertContains(resposta, 'data-table-wrap="materials"')
        self.assertContains(resposta, '<tbody data-items="materials">')
        self.assertContains(resposta, 'data-table-wrap="services"')

    def test_catalogo_expoe_sigla_e_preco_unitario_calculado(self):
        material = Material.objects.create(
            nome="Caixa de conectores",
            unidade_medida=self.unidade,
            forma_compra=Material.FormaCompra.CAIXA,
            preco_unitario=Decimal("0"),
            preco_caixa=Decimal("120"),
            quantidade_unidades_caixa=12,
            tipo_uso=Material.TipoUso.FORNECIDO,
        )

        resposta = self.client.get("/orcamentos/novo/")

        item_catalogo = next(
            item
            for item in resposta.context["dados_catalogos"]["materials"]
            if item["id"] == material.pk
        )
        self.assertEqual(item_catalogo["unidade"], "UN")
        self.assertEqual(item_catalogo["preco_unitario"], Decimal("10.00"))

    def test_edicao_usa_o_mesmo_construtor_e_carrega_os_itens(self):
        material = Material.objects.create(
            nome="Disjuntor bipolar",
            unidade_medida=self.unidade,
            preco_unitario=Decimal("50"),
            tipo_uso=Material.TipoUso.FORNECIDO,
        )
        orcamento = Orcamento.objects.create(
            validade=date.today() + timedelta(days=15),
            cliente_nome="Cliente original",
        )
        MaterialFornecido.objects.create(
            orcamento=orcamento,
            material=material,
            descricao=material.nome,
            unidade="un",
            quantidade=Decimal("2"),
            preco_unitario=Decimal("50"),
        )

        resposta = self.client.get(f"/orcamentos/{orcamento.pk}/editar/")

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "orcamentos/novo.html")
        self.assertContains(resposta, 'id="quote-form"')
        self.assertContains(resposta, "Editar orçamento")
        self.assertContains(resposta, orcamento.numero)
        self.assertNotContains(resposta, 'name="numero"')
        itens = resposta.context["dados_itens"]["materials"]
        self.assertEqual(itens[0]["catalogId"], material.pk)
        self.assertEqual(itens[0]["quantity"], "2.000")

    def test_edicao_preserva_snapshot_apos_mudar_material_do_catalogo(self):
        peca, _ = UnidadeMedida.objects.get_or_create(
            sigla="PÇ",
            defaults={"nome": "Peça"},
        )
        material = Material.objects.create(
            nome="Conector",
            unidade_medida=self.unidade,
            preco_unitario=Decimal("10"),
            tipo_uso=Material.TipoUso.FORNECIDO,
        )
        orcamento = Orcamento.objects.create(
            validade=date.today() + timedelta(days=15),
            cliente_nome="Cliente",
        )
        MaterialFornecido.objects.create(
            orcamento=orcamento,
            material=material,
            descricao=material.nome,
            unidade="UN",
            quantidade=Decimal("1"),
            preco_unitario=Decimal("10"),
        )
        material.unidade_medida = peca
        material.preco_unitario = Decimal("99")
        material.save()

        resposta = self.client.get(f"/orcamentos/{orcamento.pk}/editar/")

        item_salvo = resposta.context["dados_itens"]["materials"][0]
        item_catalogo = next(
            item
            for item in resposta.context["dados_catalogos"]["materials"]
            if item["id"] == material.pk
        )
        self.assertEqual(item_salvo["unit"], "UN")
        self.assertEqual(item_salvo["unitPrice"], "10.00")
        self.assertEqual(item_catalogo["unidade"], "PÇ")
        self.assertEqual(item_catalogo["preco_unitario"], Decimal("99.00"))

    def test_edicao_substitui_itens_e_preserva_numero_automatico(self):
        material = Material.objects.create(
            nome="Barramento",
            unidade_medida=self.unidade,
            preco_unitario=Decimal("25"),
            tipo_uso=Material.TipoUso.FORNECIDO,
        )
        orcamento = Orcamento.objects.create(
            validade=date.today() + timedelta(days=15),
            cliente_nome="Cliente original",
        )
        MaterialFornecido.objects.create(
            orcamento=orcamento,
            material=material,
            descricao=material.nome,
            unidade="un",
            quantidade=Decimal("1"),
            preco_unitario=Decimal("25"),
        )
        numero_original = orcamento.numero
        itens = {
            "materials": [
                {
                    "catalogId": material.pk,
                    "quantity": 3,
                    "unit": "un",
                    "unitPrice": 25,
                    "supplier": "Fornecedor atualizado",
                }
            ]
        }

        resposta = self.client.post(
            f"/orcamentos/{orcamento.pk}/editar/",
            self._dados_formulario(
                cliente_nome="Cliente atualizado",
                itens=itens,
                numero="NUMERO-MANUAL-IGNORADO",
            ),
        )

        self.assertEqual(resposta.status_code, 302)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.numero, numero_original)
        self.assertEqual(orcamento.cliente_nome, "Cliente atualizado")
        self.assertEqual(orcamento.materiais_fornecidos.count(), 1)
        item = orcamento.materiais_fornecidos.get()
        self.assertEqual(item.quantidade, Decimal("3.000"))
        self.assertEqual(item.subtotal, Decimal("75.00"))
        self.assertEqual(orcamento.total_final, Decimal("75.00"))

    def test_edicao_invalida_mantem_dados_e_itens_anteriores(self):
        material = Material.objects.create(
            nome="Quadro de distribuição",
            unidade_medida=self.unidade,
            preco_unitario=Decimal("100"),
            tipo_uso=Material.TipoUso.FORNECIDO,
        )
        orcamento = Orcamento.objects.create(
            validade=date.today() + timedelta(days=15),
            cliente_nome="Cliente original",
        )
        item_original = MaterialFornecido.objects.create(
            orcamento=orcamento,
            material=material,
            descricao=material.nome,
            unidade="un",
            quantidade=Decimal("1"),
            preco_unitario=Decimal("100"),
        )
        itens_invalidos = {
            "materials": [
                {
                    "catalogId": material.pk,
                    "quantity": 0,
                    "unit": "un",
                    "unitPrice": 100,
                    "supplier": "",
                }
            ]
        }

        resposta = self.client.post(
            f"/orcamentos/{orcamento.pk}/editar/",
            self._dados_formulario(
                cliente_nome="Alteração que deve ser revertida",
                itens=itens_invalidos,
            ),
        )

        self.assertEqual(resposta.status_code, 200)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.cliente_nome, "Cliente original")
        self.assertTrue(
            MaterialFornecido.objects.filter(pk=item_original.pk).exists()
        )
        self.assertEqual(orcamento.materiais_fornecidos.count(), 1)

    def test_proposta_pdf_abre_para_impressao_sem_dados_internos(self):
        configuracao = Configuracao.carregar()
        configuracao.nome_eletricista = "Eletricista João"
        configuracao.telefone = "(48) 99999-9999"
        configuracao.mostrar_deslocamento_proposta = False
        configuracao.save()
        orcamento = Orcamento.objects.create(
            data=date(2031, 4, 5),
            validade=date(2031, 4, 20),
            cliente_nome="Cliente <Teste>",
            custo_deslocamento=Decimal("25"),
            observacoes_cliente="Condições combinadas com o cliente.",
            observacoes_internas="INFORMAÇÃO INTERNA CONFIDENCIAL",
            lucro_liquido=Decimal("25"),
            total_final=Decimal("350"),
            valor_mao_obra=Decimal("200"),
            subtotal_materiais=Decimal("100"),
        )
        ItemServico.objects.create(
            orcamento=orcamento,
            descricao="Instalação de quadro",
            unidade="un",
            quantidade=Decimal("1"),
            preco_unitario=Decimal("200"),
        )

        resposta = self.client.get(
            f"/orcamentos/{orcamento.pk}/documentos/proposta.pdf"
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "application/pdf")
        self.assertIn("inline", resposta["Content-Disposition"])
        self.assertTrue(resposta.content.startswith(b"%PDF"))
        self.assertGreater(len(resposta.content), 1500)

        dados = montar_dados_proposta(orcamento, configuracao)
        self.assertNotIn(
            "deslocamento",
            [linha.codigo for linha in dados.linhas_valores],
        )
        self.assertEqual(
            sum(
                (linha.valor for linha in dados.linhas_valores),
                Decimal("0.00"),
            ),
            dados.total,
        )
        self.assertFalse(hasattr(dados, "lucro_liquido"))
        self.assertFalse(hasattr(dados, "observacoes_internas"))

    def test_proposta_pdf_pode_ser_baixada_e_respeita_deslocamento(self):
        configuracao = Configuracao.carregar()
        configuracao.mostrar_deslocamento_proposta = True
        configuracao.save()
        orcamento = Orcamento.objects.create(
            validade=date.today() + timedelta(days=15),
            cliente_nome="Cliente",
            custo_deslocamento=Decimal("25"),
            total_final=Decimal("25"),
        )

        resposta = self.client.get(
            f"/orcamentos/{orcamento.pk}/documentos/proposta.pdf?download=1"
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("attachment", resposta["Content-Disposition"])
        dados = montar_dados_proposta(orcamento, configuracao)
        deslocamento = next(
            linha
            for linha in dados.linhas_valores
            if linha.codigo == "deslocamento"
        )
        self.assertEqual(deslocamento.valor, Decimal("25.00"))

    def test_proposta_pdf_bloqueia_composicao_aberta_com_status_422(self):
        orcamento = Orcamento.objects.create(
            validade=date.today() + timedelta(days=15),
            cliente_nome="Cliente",
            subtotal_materiais=Decimal("99.90"),
            valor_mao_obra=Decimal("360.00"),
            total_final=Decimal("630.83"),
        )

        resposta = self.client.get(
            f"/orcamentos/{orcamento.pk}/documentos/proposta.pdf"
        )

        self.assertEqual(resposta.status_code, 422)
        self.assertNotEqual(
            resposta["Content-Type"],
            "application/pdf",
        )
        self.assertContains(
            resposta,
            "O PDF não foi gerado",
            status_code=422,
        )
        self.assertContains(
            resposta,
            "170,93",
            status_code=422,
        )
        self.assertContains(
            resposta,
            "Valores ainda não distribuídos",
            status_code=422,
        )
        self.assertContains(
            resposta,
            "Diferença entre o resumo interno e o total final",
            status_code=422,
        )

    def test_novo_e_edicao_persistem_modo_de_apresentacao(self):
        material = Material.objects.create(
            nome="Disjuntor",
            unidade_medida=self.unidade,
            preco_unitario=Decimal("40.00"),
            tipo_uso=Material.TipoUso.FORNECIDO,
        )
        itens = {
            "materials": [
                {
                    "catalogId": material.pk,
                    "quantity": 1,
                    "unit": "UN",
                    "unitPrice": 40,
                    "supplier": "",
                }
            ]
        }

        resposta = self.client.post(
            "/orcamentos/novo/",
            self._dados_formulario(
                cliente_nome="Cliente",
                itens=itens,
                modo_apresentacao=(
                    Orcamento.ModoApresentacao.PRECO_GLOBAL
                ),
            ),
        )

        self.assertEqual(resposta.status_code, 302)
        orcamento = Orcamento.objects.get()
        self.assertEqual(
            orcamento.modo_apresentacao,
            Orcamento.ModoApresentacao.PRECO_GLOBAL,
        )
        resposta_edicao = self.client.get(
            f"/orcamentos/{orcamento.pk}/editar/"
        )
        self.assertEqual(
            resposta_edicao.context["form"]["modo_apresentacao"].value(),
            Orcamento.ModoApresentacao.PRECO_GLOBAL,
        )

        resposta = self.client.post(
            f"/orcamentos/{orcamento.pk}/editar/",
            self._dados_formulario(
                cliente_nome="Cliente",
                itens=itens,
                modo_apresentacao=Orcamento.ModoApresentacao.DETALHADO,
            ),
        )

        self.assertEqual(resposta.status_code, 302)
        orcamento.refresh_from_db()
        self.assertEqual(
            orcamento.modo_apresentacao,
            Orcamento.ModoApresentacao.DETALHADO,
        )

    def test_novo_orcamento_salva_todos_os_itens_e_totais(self):
        material = Material.objects.create(
            nome="Disjuntor",
            unidade_medida=self.unidade,
            preco_unitario=Decimal("40"),
            tipo_uso=Material.TipoUso.FORNECIDO,
        )
        insumo = Material.objects.create(
            nome="Fita isolante",
            unidade_medida=self.unidade,
            preco_unitario=Decimal("10"),
            tipo_uso=Material.TipoUso.INSUMO,
        )
        servico = Servico.objects.create(
            nome="Instalação de tomada",
            unidade="un",
            preco_unitario=Decimal("80"),
        )
        dificuldade = Dificuldade.objects.create(nome="Média", percentual=10)
        altura = TrabalhoAltura.objects.create(nome="Escada", percentual=10)
        veiculo = Veiculo.objects.create(
            nome="Carro", km_por_litro=10, preco_combustivel=6
        )
        itens = {
            "materials": [
                {
                    "catalogId": material.pk,
                    "quantity": 2,
                    "unit": "",
                    "unitPrice": 40,
                    "supplier": "",
                }
            ],
            "clientMaterials": [
                {
                    "referenceId": None,
                    "description": "Cabo 2,5 mm²",
                    "quantity": 20,
                    "unit": "m",
                    "note": "",
                }
            ],
            "supplies": [
                {
                    "catalogId": insumo.pk,
                    "quantity": 1,
                    "unit": "",
                    "unitPrice": 10,
                }
            ],
            "services": [
                {
                    "serviceId": servico.pk,
                    "quantity": 2,
                    "unitPrice": 80,
                    "difficultyId": dificuldade.pk,
                    "heightId": altura.pk,
                }
            ],
            "otherCosts": [{"description": "Estacionamento", "value": 10}],
        }
        resposta = self.client.post(
            "/orcamentos/novo/",
            {
                "numero": "",
                "data": date.today().isoformat(),
                "validade": (date.today() + timedelta(days=15)).isoformat(),
                "status": Orcamento.Status.RASCUNHO,
                "modo_apresentacao": Orcamento.ModoApresentacao.DETALHADO,
                "cliente_nome": "Maria",
                "cliente_telefone": "",
                "endereco_obra": "",
                "veiculo": veiculo.pk,
                "distancia_km": "100",
                "metodo_mao_obra": Orcamento.MetodoMaoObra.SERVICOS,
                "tempo_estimado_horas": "0",
                "valor_hora": "0",
                "percentual_ferramentas": "10",
                "percentual_empresa": "10",
                "percentual_lucro": "20",
                "desconto": "0",
                "observacoes_internas": "",
                "observacoes_cliente": "",
                "itens_json": json.dumps(itens),
            },
        )

        self.assertEqual(resposta.status_code, 302)
        orcamento = Orcamento.objects.get()
        self.assertEqual(orcamento.materiais_fornecidos.count(), 1)
        self.assertEqual(orcamento.materiais_cliente.count(), 1)
        self.assertEqual(orcamento.insumos_internos.count(), 1)
        self.assertEqual(
            orcamento.materiais_fornecidos.get().unidade,
            self.unidade.sigla,
        )
        self.assertEqual(
            orcamento.insumos_internos.get().unidade,
            self.unidade.sigla,
        )
        self.assertEqual(orcamento.servicos.count(), 1)
        self.assertEqual(orcamento.outros_custos.count(), 1)
        self.assertEqual(orcamento.subtotal_servicos_final, Decimal("192.00"))
        self.assertGreater(orcamento.total_final, Decimal("0"))

    def test_novo_orcamento_vazio_nao_e_persistido(self):
        resposta = self.client.post(
            "/orcamentos/novo/",
            {
                "numero": "",
                "data": date.today().isoformat(),
                "validade": (date.today() + timedelta(days=15)).isoformat(),
                "status": Orcamento.Status.RASCUNHO,
                "modo_apresentacao": Orcamento.ModoApresentacao.DETALHADO,
                "cliente_nome": "Maria",
                "veiculo": "",
                "distancia_km": "0",
                "metodo_mao_obra": Orcamento.MetodoMaoObra.SERVICOS,
                "tempo_estimado_horas": "0",
                "valor_hora": "0",
                "percentual_ferramentas": "0",
                "percentual_empresa": "0",
                "percentual_lucro": "0",
                "desconto": "0",
                "itens_json": "{}",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Orcamento.objects.count(), 0)
