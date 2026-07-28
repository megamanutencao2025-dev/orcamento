from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from cadastros.models import Dificuldade, Material, Servico, TrabalhoAltura

from .models import (
    InsumoInterno,
    ItemServico,
    MaterialCliente,
    MaterialFornecido,
    Orcamento,
    OutroCusto,
)

ZERO = Decimal("0.00")
CENTAVOS = Decimal("0.01")


def _total(queryset, campo):
    return queryset.aggregate(total=Sum(campo))["total"] or ZERO


def calcular_orcamento(orcamento: Orcamento) -> Orcamento:
    """Recalcula e persiste todos os totais internos do orçamento."""

    orcamento.subtotal_materiais = _total(
        orcamento.materiais_fornecidos, "subtotal"
    )
    orcamento.subtotal_insumos = _total(orcamento.insumos_internos, "subtotal")
    orcamento.subtotal_servicos_base = _total(
        orcamento.servicos, "subtotal_base"
    )
    orcamento.total_dificuldade = _total(
        orcamento.servicos, "valor_dificuldade"
    )
    orcamento.total_altura = _total(orcamento.servicos, "valor_altura")
    orcamento.subtotal_servicos_final = _total(
        orcamento.servicos, "subtotal_final"
    )
    orcamento.outros_custos_total = _total(orcamento.outros_custos, "valor")

    if orcamento.veiculo_id and orcamento.veiculo.km_por_litro > ZERO:
        orcamento.custo_deslocamento = (
            orcamento.distancia_km
            / orcamento.veiculo.km_por_litro
            * orcamento.veiculo.preco_combustivel
        ).quantize(CENTAVOS)
    else:
        orcamento.custo_deslocamento = ZERO

    orcamento.custos_diretos = (
        orcamento.subtotal_materiais
        + orcamento.subtotal_insumos
        + orcamento.custo_deslocamento
        + orcamento.outros_custos_total
    )
    if orcamento.metodo_mao_obra == Orcamento.MetodoMaoObra.SERVICOS:
        orcamento.valor_mao_obra = orcamento.subtotal_servicos_final
    else:
        orcamento.valor_mao_obra = (
            orcamento.tempo_estimado_horas * orcamento.valor_hora
        ).quantize(CENTAVOS)

    orcamento.reserva_ferramentas = (
        orcamento.valor_mao_obra
        * orcamento.percentual_ferramentas
        / Decimal("100")
    ).quantize(CENTAVOS)
    orcamento.subtotal_operacional = (
        orcamento.custos_diretos
        + orcamento.valor_mao_obra
        + orcamento.reserva_ferramentas
    )
    orcamento.reserva_empresa = (
        orcamento.subtotal_operacional
        * orcamento.percentual_empresa
        / Decimal("100")
    ).quantize(CENTAVOS)
    orcamento.subtotal_antes_lucro = (
        orcamento.subtotal_operacional + orcamento.reserva_empresa
    )
    orcamento.lucro_liquido = (
        orcamento.subtotal_antes_lucro
        * orcamento.percentual_lucro
        / Decimal("100")
    ).quantize(CENTAVOS)
    total_antes_desconto = (
        orcamento.subtotal_antes_lucro + orcamento.lucro_liquido
    )
    if orcamento.desconto > total_antes_desconto:
        raise ValidationError(
            "O desconto não pode ser maior que o valor total antes do desconto."
        )
    orcamento.total_final = total_antes_desconto - orcamento.desconto
    orcamento.save()
    return orcamento


def _decimal(valor, nome, positivo=False):
    try:
        numero = Decimal(str(valor).replace(",", "."))
    except (ArithmeticError, TypeError, ValueError):
        raise ValidationError(f"{nome}: informe um número válido.") from None
    if not numero.is_finite():
        raise ValidationError(f"{nome}: informe um número finito.") from None
    if positivo and numero <= ZERO:
        raise ValidationError(f"{nome} deve ser maior que zero.")
    if not positivo and numero < ZERO:
        raise ValidationError(f"{nome} não pode ser negativo.")
    return numero


def _obter(model, pk, nome):
    try:
        return model.objects.get(pk=pk, ativo=True)
    except (model.DoesNotExist, TypeError, ValueError):
        raise ValidationError(f"{nome} selecionado não está disponível.") from None


@transaction.atomic
def salvar_itens_completos(
    orcamento: Orcamento, dados: dict, *, substituir=False
) -> Orcamento:
    """Valida e persiste os itens enviados pelo construtor de orçamento."""

    secoes = ("materials", "clientMaterials", "supplies", "services", "otherCosts")
    if not isinstance(dados, dict) or not any(dados.get(secao) for secao in secoes):
        raise ValidationError(
            "Adicione ao menos um material, insumo, serviço ou outro custo."
        )
    for secao in secoes:
        if not isinstance(dados.get(secao, []), list):
            raise ValidationError("A lista de itens enviada é inválida.")
        if not all(isinstance(item, dict) for item in dados.get(secao, [])):
            raise ValidationError("Um dos itens enviados é inválido.")

    if substituir:
        orcamento.materiais_fornecidos.all().delete()
        orcamento.materiais_cliente.all().delete()
        orcamento.insumos_internos.all().delete()
        orcamento.servicos.all().delete()
        orcamento.outros_custos.all().delete()

    for dados_item in dados.get("materials", []):
        material = _obter(Material, dados_item.get("catalogId"), "Material")
        if material.tipo_uso != Material.TipoUso.FORNECIDO:
            raise ValidationError("Selecione um material do tipo fornecido/cobrado.")
        MaterialFornecido.objects.create(
            orcamento=orcamento,
            material=material,
            descricao=material.nome,
            quantidade=_decimal(
                dados_item.get("quantity"), "Quantidade do material", positivo=True
            ),
            unidade=(
                dados_item.get("unit") or material.unidade_sigla
            ).strip(),
            preco_unitario=_decimal(
                dados_item.get("unitPrice"), "Preço do material"
            ),
            fornecedor=(dados_item.get("supplier") or material.fornecedor).strip(),
        )

    for dados_item in dados.get("clientMaterials", []):
        descricao = (dados_item.get("description") or "").strip()
        if not descricao:
            raise ValidationError("Informe a descrição do material para o cliente.")
        unidade = (dados_item.get("unit") or "").strip()
        if not unidade:
            raise ValidationError("Informe a unidade do material para o cliente.")
        referencia = None
        if dados_item.get("referenceId"):
            referencia = _obter(
                Material, dados_item["referenceId"], "Material de referência"
            )
        MaterialCliente.objects.create(
            orcamento=orcamento,
            material_referencia=referencia,
            descricao=descricao,
            quantidade=_decimal(
                dados_item.get("quantity"), "Quantidade para o cliente", positivo=True
            ),
            unidade=unidade,
            observacao=(dados_item.get("note") or "").strip(),
        )

    for dados_item in dados.get("supplies", []):
        material = _obter(Material, dados_item.get("catalogId"), "Insumo")
        if material.tipo_uso != Material.TipoUso.INSUMO:
            raise ValidationError("Selecione um material do tipo insumo interno.")
        InsumoInterno.objects.create(
            orcamento=orcamento,
            material=material,
            descricao=material.nome,
            quantidade=_decimal(
                dados_item.get("quantity"), "Quantidade do insumo", positivo=True
            ),
            unidade=(
                dados_item.get("unit") or material.unidade_sigla
            ).strip(),
            preco_unitario=_decimal(
                dados_item.get("unitPrice"), "Preço do insumo"
            ),
        )

    for dados_item in dados.get("services", []):
        servico = _obter(Servico, dados_item.get("serviceId"), "Serviço")
        dificuldade = (
            _obter(Dificuldade, dados_item["difficultyId"], "Dificuldade")
            if dados_item.get("difficultyId")
            else None
        )
        altura = (
            _obter(TrabalhoAltura, dados_item["heightId"], "Trabalho em altura")
            if dados_item.get("heightId")
            else None
        )
        ItemServico.objects.create(
            orcamento=orcamento,
            servico=servico,
            descricao=servico.nome,
            unidade=servico.unidade,
            quantidade=_decimal(
                dados_item.get("quantity"), "Quantidade do serviço", positivo=True
            ),
            preco_unitario=_decimal(
                dados_item.get("unitPrice"), "Preço do serviço"
            ),
            dificuldade=dificuldade,
            altura=altura,
        )

    for dados_item in dados.get("otherCosts", []):
        descricao = (dados_item.get("description") or "").strip()
        if not descricao:
            raise ValidationError("Informe a descrição do outro custo.")
        OutroCusto.objects.create(
            orcamento=orcamento,
            descricao=descricao,
            valor=_decimal(dados_item.get("value"), "Valor do outro custo"),
        )

    return calcular_orcamento(orcamento)
