from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from core.models import Configuracao

from ..composicao_comercial import (
    LinhaComercial,
    montar_composicao_comercial,
    validar_fechamento,
)
from ..models import Orcamento


@dataclass(frozen=True, slots=True)
class ServicoProposta:
    descricao: str
    quantidade: Decimal
    unidade: str


@dataclass(frozen=True, slots=True)
class MaterialCompraProposta:
    descricao: str
    quantidade: Decimal
    unidade: str
    observacao: str


@dataclass(frozen=True, slots=True)
class MaterialInclusoProposta:
    descricao: str
    quantidade: Decimal
    unidade: str


@dataclass(frozen=True, slots=True)
class PropostaDados:
    profissional: str
    contatos_profissional: tuple[str, ...]
    numero: str
    data: date
    validade: date
    cliente: str
    telefone_cliente: str
    endereco_obra: str
    modo_apresentacao: str
    linhas_valores: tuple[LinhaComercial, ...]
    total: Decimal
    servicos: tuple[ServicoProposta, ...]
    materiais_inclusos: tuple[MaterialInclusoProposta, ...]
    materiais_compra: tuple[MaterialCompraProposta, ...]
    observacoes: str


def montar_dados_proposta(
    orcamento: Orcamento, configuracao: Configuracao
) -> PropostaDados:
    """Seleciona somente informações permitidas na proposta do cliente."""

    servicos_origem = getattr(orcamento, "servicos_proposta", None)
    if servicos_origem is None:
        servicos_origem = orcamento.servicos.order_by("pk")
    materiais_origem = getattr(orcamento, "materiais_compra_proposta", None)
    if materiais_origem is None:
        materiais_origem = orcamento.materiais_cliente.order_by("pk")
    materiais_inclusos_origem = getattr(
        orcamento, "materiais_inclusos_proposta", None
    )
    if materiais_inclusos_origem is None:
        materiais_inclusos_origem = orcamento.materiais_fornecidos.order_by(
            "pk"
        )

    contatos = tuple(
        valor
        for valor in (
            configuracao.telefone,
            configuracao.email,
            configuracao.cidade,
        )
        if valor
    )
    servicos = tuple(
        ServicoProposta(
            descricao=item.descricao,
            quantidade=item.quantidade,
            unidade=item.unidade,
        )
        for item in servicos_origem
    )
    materiais_compra = tuple(
        MaterialCompraProposta(
            descricao=item.descricao,
            quantidade=item.quantidade,
            unidade=item.unidade,
            observacao=item.observacao,
        )
        for item in materiais_origem
    )
    materiais_inclusos = tuple(
        MaterialInclusoProposta(
            descricao=item.descricao,
            quantidade=item.quantidade,
            unidade=item.unidade,
        )
        for item in materiais_inclusos_origem
    )
    composicao = montar_composicao_comercial(
        orcamento,
        mostrar_deslocamento=configuracao.mostrar_deslocamento_proposta,
    )
    if orcamento.modo_apresentacao == Orcamento.ModoApresentacao.PRECO_GLOBAL:
        linhas_valores = (
            LinhaComercial(
                codigo="preco_global",
                descricao="TOTAL DA PROPOSTA",
                valor=composicao.total_final,
            ),
        )
    else:
        linhas_valores = composicao.linhas
    validar_fechamento(linhas_valores, composicao.total_final)

    return PropostaDados(
        profissional=configuracao.nome_eletricista or "Serviços elétricos",
        contatos_profissional=contatos,
        numero=orcamento.numero,
        data=orcamento.data,
        validade=orcamento.validade,
        cliente=orcamento.cliente_nome,
        telefone_cliente=orcamento.cliente_telefone,
        endereco_obra=orcamento.endereco_obra,
        modo_apresentacao=orcamento.modo_apresentacao,
        linhas_valores=linhas_valores,
        total=composicao.total_final,
        servicos=servicos,
        materiais_inclusos=materiais_inclusos,
        materiais_compra=materiais_compra,
        observacoes=orcamento.observacoes_cliente,
    )
