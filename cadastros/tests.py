import json
import socket
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from .forms import CategoriaMaterialForm, MaterialForm, UnidadeMedidaForm
from .models import CategoriaMaterial, Material, UnidadeMedida
from .services.product_import import (
    ProductPreview,
    UnsafeProductUrl,
    extract_product,
    import_product,
    validate_product_url,
)


class CategoriaMaterialTests(TestCase):
    def test_categoria_pode_ser_vinculada_ao_material(self):
        categoria = CategoriaMaterial.objects.create(nome="Disjuntores")
        unidade = UnidadeMedida.objects.get(sigla="UN")
        material = Material.objects.create(
            nome="Disjuntor bipolar",
            categoria=categoria,
            unidade_medida=unidade,
            preco_unitario=Decimal("42.00"),
            tipo_uso=Material.TipoUso.FORNECIDO,
        )

        self.assertEqual(material.categoria, categoria)
        self.assertEqual(categoria.materiais.get(), material)

    def test_nome_de_categoria_nao_pode_repetir_ignorando_maiusculas(self):
        CategoriaMaterial.objects.create(nome="Barramentos")
        form = CategoriaMaterialForm(
            {"nome": "barramentos", "descricao": ""}
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Já existe", form.errors["nome"][0])


class UnidadeMedidaTests(TestCase):
    def test_migracao_disponibiliza_unidades_padrao(self):
        self.assertSetEqual(
            set(UnidadeMedida.objects.values_list("sigla", flat=True)),
            {
                "UN",
                "PÇ",
                "M",
                "M²",
                "M³",
                "CM",
                "MM",
                "KG",
                "G",
                "L",
                "ML",
                "RL",
                "PCT",
                "CX",
                "JG",
                "PAR",
            },
        )

    def test_normaliza_sigla_e_impede_duplicidade_sem_diferenciar_caixa(self):
        unidade = UnidadeMedida.objects.create(
            nome="  Bobina  ",
            sigla=" bob ",
        )

        self.assertEqual(unidade.nome, "Bobina")
        self.assertEqual(unidade.sigla, "BOB")

        form = UnidadeMedidaForm(
            {"nome": "Outra unidade", "sigla": "bob", "ativo": True}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Já existe", form.errors["sigla"][0])

    def test_material_oferece_somente_unidades_ativas(self):
        ativa = UnidadeMedida.objects.get(sigla="UN")
        inativa = UnidadeMedida.objects.get(sigla="PÇ")
        inativa.ativo = False
        inativa.save(update_fields={"ativo"})

        form = MaterialForm()

        self.assertIn(ativa, form.fields["unidade_medida"].queryset)
        self.assertNotIn(inativa, form.fields["unidade_medida"].queryset)

    def test_edicao_preserva_unidade_que_foi_desativada(self):
        inativa = UnidadeMedida.objects.get(sigla="PÇ")
        inativa.ativo = False
        inativa.save(update_fields={"ativo"})
        material = Material.objects.create(
            nome="Conector",
            unidade_medida=inativa,
            preco_unitario=Decimal("2.50"),
            tipo_uso=Material.TipoUso.FORNECIDO,
        )

        form = MaterialForm(instance=material)

        self.assertIn(inativa, form.fields["unidade_medida"].queryset)

    def test_unidade_em_uso_nao_pode_ser_excluida(self):
        unidade = UnidadeMedida.objects.get(sigla="UN")
        Material.objects.create(
            nome="Disjuntor",
            unidade_medida=unidade,
            preco_unitario=Decimal("20.00"),
            tipo_uso=Material.TipoUso.FORNECIDO,
        )

        response = self.client.post(
            f"/cadastros/unidades/{unidade.pk}/excluir/",
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(UnidadeMedida.objects.filter(pk=unidade.pk).exists())
        self.assertContains(response, "Desative-o para manter o histórico")

    def test_area_de_unidades_permite_cadastrar_e_desativar(self):
        response = self.client.post(
            "/cadastros/unidades/",
            {"nome": "Galão", "sigla": "gl", "ativo": True},
        )

        self.assertEqual(response.status_code, 302)
        unidade = UnidadeMedida.objects.get(sigla="GL")
        self.assertTrue(unidade.ativo)

        response = self.client.post(
            f"/cadastros/unidades/?editar={unidade.pk}",
            {"nome": "Galão", "sigla": "GL"},
        )

        self.assertEqual(response.status_code, 302)
        unidade.refresh_from_db()
        self.assertFalse(unidade.ativo)


class MaterialFormaCompraTests(TestCase):
    def setUp(self):
        self.unidade = UnidadeMedida.objects.get(sigla="UN")

    def dados_formulario(self, **alteracoes):
        dados = {
            "nome": "Disjuntor 20A",
            "categoria": "",
            "forma_compra": Material.FormaCompra.UNIDADE,
            "unidade_medida": self.unidade.pk,
            "quantidade_unidades_caixa": "",
            "preco_compra": "21.50",
            "fornecedor": "Fornecedor",
            "tipo_uso": Material.TipoUso.FORNECIDO,
            "imagem_url": "",
            "url_origem": "",
            "fonte_importacao": "",
        }
        dados.update(alteracoes)
        return dados

    def test_compra_por_unidade_salva_preco_diretamente(self):
        form = MaterialForm(
            self.dados_formulario(quantidade_unidades_caixa="12")
        )

        self.assertTrue(form.is_valid(), form.errors)
        material = form.save()

        self.assertEqual(material.preco_unitario, Decimal("21.50"))
        self.assertIsNone(material.preco_caixa)
        self.assertIsNone(material.quantidade_unidades_caixa)

    def test_compra_por_caixa_preserva_total_e_calcula_preco_unitario(self):
        form = MaterialForm(
            self.dados_formulario(
                forma_compra=Material.FormaCompra.CAIXA,
                preco_compra="120.00",
                quantidade_unidades_caixa="12",
                preco_unitario_calculado="999.00",
            )
        )

        self.assertTrue(form.is_valid(), form.errors)
        material = form.save()

        self.assertEqual(material.preco_caixa, Decimal("120.00"))
        self.assertEqual(material.quantidade_unidades_caixa, 12)
        self.assertEqual(material.preco_unitario, Decimal("10.00"))
        self.assertEqual(material.preco_compra, Decimal("120.00"))

    def test_preco_unitario_da_caixa_e_arredondado_em_duas_casas(self):
        form = MaterialForm(
            self.dados_formulario(
                forma_compra=Material.FormaCompra.CAIXA,
                preco_compra="100.00",
                quantidade_unidades_caixa="12",
            )
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().preco_unitario, Decimal("8.33"))

    def test_quantidade_da_caixa_e_obrigatoria(self):
        form = MaterialForm(
            self.dados_formulario(
                forma_compra=Material.FormaCompra.CAIXA,
                preco_compra="120.00",
                quantidade_unidades_caixa="",
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("quantidade_unidades_caixa", form.errors)

    def test_modelo_recalcula_preco_unitario_ao_salvar_caixa(self):
        material = Material(
            nome="Caixa de conectores",
            unidade_medida=self.unidade,
            forma_compra=Material.FormaCompra.CAIXA,
            preco_caixa=Decimal("45.00"),
            quantidade_unidades_caixa=10,
            preco_unitario=Decimal("999.00"),
            tipo_uso=Material.TipoUso.INSUMO,
        )

        material.save()

        self.assertEqual(material.preco_unitario, Decimal("4.50"))


class ProductExtractorTests(TestCase):
    def test_extrai_json_ld_do_mercado_livre(self):
        html = """
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Disjuntor Elgin 20A",
          "image": ["https://http2.mlstatic.com/produto.jpg"],
          "offers": {
            "@type": "Offer",
            "price": "19.90",
            "priceCurrency": "BRL"
          }
        }
        </script>
        """

        product = extract_product(
            html,
            "https://produto.mercadolivre.com.br/MLB-123",
            "Mercado Livre",
        )

        self.assertEqual(product.name, "Disjuntor Elgin 20A")
        self.assertEqual(product.price, Decimal("19.90"))
        self.assertEqual(
            product.image_url, "https://http2.mlstatic.com/produto.jpg"
        )
        self.assertEqual(product.confidence, "high")

    def test_extrai_metadados_da_shopee(self):
        html = """
        <meta property="og:title" content="Barramento pente bipolar">
        <meta property="og:image" content="https://cf.shopee.com.br/item.jpg">
        <meta property="product:price:amount" content="35.80">
        <meta property="product:price:currency" content="BRL">
        """

        product = extract_product(
            html, "https://shopee.com.br/produto-i.1.2", "Shopee"
        )

        self.assertEqual(product.name, "Barramento pente bipolar")
        self.assertEqual(product.price, Decimal("35.80"))

    def test_extrai_preco_visual_da_amazon(self):
        html = """
        <html><head><meta property="og:image"
        content="https://m.media-amazon.com/images/item.jpg"></head>
        <body><span id="productTitle">Disjuntor DIN 32A</span>
        <span class="a-price"><span class="a-offscreen">R$ 27,49</span></span>
        </body></html>
        """

        product = extract_product(
            html, "https://www.amazon.com.br/dp/ABC", "Amazon"
        )

        self.assertEqual(product.name, "Disjuntor DIN 32A")
        self.assertEqual(product.price, Decimal("27.49"))

    def test_extrai_preco_vtex_da_delupo(self):
        html = """
        <meta property="og:title" content="Alicate profissional - Delupo">
        <meta property="og:image" content="/arquivos/alicate.jpg">
        <span class="vtex-product-price-1-x-sellingPriceValue">R$ 1.799,00</span>
        """

        product = extract_product(
            html, "https://www.delupo.com.br/alicate/p", "Delupo"
        )

        self.assertEqual(product.name, "Alicate profissional")
        self.assertEqual(product.price, Decimal("1799.00"))
        self.assertEqual(
            product.image_url, "https://www.delupo.com.br/arquivos/alicate.jpg"
        )

    @patch("cadastros.services.product_import._fetch_json")
    @patch("cadastros.services.product_import.validate_product_url")
    def test_delupo_prioriza_catalogo_vtex(self, validate_url, fetch_json):
        url = "https://www.delupo.com.br/alicate-universal/p"
        validate_url.return_value = (url, "Delupo")
        fetch_json.return_value = [
            {
                "productName": "Alicate universal isolado",
                "items": [
                    {
                        "images": [{"imageUrl": "https://cdn.delupo.com/item.jpg"}],
                        "sellers": [
                            {
                                "commertialOffer": {
                                    "Price": 89.9,
                                    "IsAvailable": True,
                                }
                            }
                        ],
                    }
                ],
            }
        ]

        product = import_product(url)

        self.assertEqual(product.name, "Alicate universal isolado")
        self.assertEqual(product.price, Decimal("89.90"))
        self.assertEqual(product.source, "catálogo da loja")

    @patch("cadastros.services.product_import.fetch_product_html")
    @patch("cadastros.services.product_import.validate_product_url")
    def test_mercado_livre_bloqueado_retorna_previa_parcial(
        self, validate_url, fetch_html
    ):
        url = (
            "https://produto.mercadolivre.com.br/"
            "MLB-123-disjuntor-bipolar-20a-_JM"
        )
        validate_url.return_value = (url, "Mercado Livre")
        fetch_html.return_value = (
            "<title>Mercado Libre</title>",
            "https://www.mercadolivre.com.br/gz/account-verification",
            "Mercado Livre",
        )

        product = import_product(url)

        self.assertEqual(product.name, "Disjuntor Bipolar 20A")
        self.assertIsNone(product.price)
        self.assertEqual(product.confidence, "low")

    def test_bloqueia_dominio_nao_suportado(self):
        with self.assertRaises(UnsafeProductUrl):
            validate_product_url(
                "https://example.com/produto", resolve_dns=False
            )

    @patch("cadastros.services.product_import.socket.getaddrinfo")
    def test_bloqueia_endereco_privado(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))
        ]

        with self.assertRaises(UnsafeProductUrl):
            validate_product_url("https://www.amazon.com.br/produto")


class MaterialImportViewsTests(TestCase):
    def test_pagina_exibe_importador_categorias_e_unidades(self):
        response = self.client.get("/cadastros/materiais/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Importar produto por URL")
        self.assertContains(response, "Categorias")
        self.assertContains(response, "Unidades de medida")
        self.assertContains(response, "Forma de compra")
        self.assertNotContains(response, 'name="unidade"')

    @patch("cadastros.views.import_product")
    def test_endpoint_retorna_previa_sem_salvar(self, importer):
        importer.return_value = ProductPreview(
            name="Disjuntor 20A",
            price=Decimal("21.50"),
            image_url="https://example-cdn.com/image.jpg",
            supplier="Mercado Livre",
            source_url="https://produto.mercadolivre.com.br/MLB-1",
            source="dados estruturados",
        )

        response = self.client.post(
            "/cadastros/materiais/importar-url/",
            data=json.dumps(
                {"url": "https://produto.mercadolivre.com.br/MLB-1"}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["product"]["price"], "21.50")
        self.assertEqual(Material.objects.count(), 0)

    def test_salva_material_importado_com_categoria_e_data(self):
        categoria = CategoriaMaterial.objects.create(nome="Disjuntores")
        unidade = UnidadeMedida.objects.get(sigla="UN")

        response = self.client.post(
            "/cadastros/materiais/",
            {
                "nome": "Disjuntor 20A",
                "categoria": categoria.pk,
                "forma_compra": Material.FormaCompra.UNIDADE,
                "unidade_medida": unidade.pk,
                "quantidade_unidades_caixa": "",
                "preco_compra": "21.50",
                "fornecedor": "Mercado Livre",
                "tipo_uso": Material.TipoUso.FORNECIDO,
                "imagem_url": "https://http2.mlstatic.com/item.jpg",
                "url_origem": "https://produto.mercadolivre.com.br/MLB-1",
                "fonte_importacao": "Mercado Livre",
            },
        )

        self.assertEqual(response.status_code, 302)
        material = Material.objects.get()
        self.assertEqual(material.categoria, categoria)
        self.assertEqual(material.unidade_medida, unidade)
        self.assertEqual(material.preco_unitario, Decimal("21.50"))
        self.assertIsNotNone(material.importado_em)

    def test_listagem_exibe_dados_de_compra_por_caixa(self):
        unidade = UnidadeMedida.objects.get(sigla="PÇ")
        Material.objects.create(
            nome="Caixa de terminais",
            unidade_medida=unidade,
            forma_compra=Material.FormaCompra.CAIXA,
            preco_caixa=Decimal("120.00"),
            quantidade_unidades_caixa=12,
            preco_unitario=Decimal("0.00"),
            tipo_uso=Material.TipoUso.INSUMO,
        )

        response = self.client.get("/cadastros/materiais/")

        self.assertContains(response, "Preço da caixa")
        self.assertContains(response, "R$ 120,00")
        self.assertContains(response, "Unidades por caixa")
        self.assertContains(response, "Preço por unidade")
        self.assertContains(response, "R$ 10,00")
        self.assertContains(response, "PÇ")
