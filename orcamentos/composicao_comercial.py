from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from .models import Orcamento

ZERO = Decimal("0.00")
CENTAVO = Decimal("0.01")


def _dinheiro(valor: Decimal) -> Decimal:
    if not isinstance(valor, Decimal):
        raise TypeError("Valores da composição comercial devem usar Decimal.")
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _moeda(valor: Decimal) -> str:
    formatado = f"{valor:,.2f}"
    formatado = formatado.replace(",", "#").replace(".", ",").replace("#", ".")
    return f"R$ {formatado}"


@dataclass(frozen=True, slots=True)
class LinhaComercial:
    codigo: str
    descricao: str
    valor: Decimal

    def __post_init__(self):
        object.__setattr__(self, "valor", _dinheiro(self.valor))


@dataclass(frozen=True, slots=True)
class ComponentePendente:
    descricao: str
    valor: Decimal

    def __post_init__(self):
        object.__setattr__(self, "valor", _dinheiro(self.valor))


@dataclass(frozen=True, slots=True)
class ComposicaoComercial:
    linhas: tuple[LinhaComercial, ...]
    total_final: Decimal

    def __post_init__(self):
        object.__setattr__(self, "total_final", _dinheiro(self.total_final))

    @property
    def total_apresentado(self) -> Decimal:
        return _dinheiro(sum((linha.valor for linha in self.linhas), ZERO))


class ComposicaoComercialInvalida(ValidationError):
    """Erro estruturado usado para impedir uma proposta que não fecha."""

    def __init__(
        self,
        *,
        total_apresentado: Decimal,
        total_final: Decimal,
        componentes_pendentes: tuple[ComponentePendente, ...] = (),
        mensagem: str | None = None,
    ):
        self.total_apresentado = _dinheiro(total_apresentado)
        self.total_final = _dinheiro(total_final)
        self.diferenca = _dinheiro(self.total_final - self.total_apresentado)
        self.diferenca_absoluta = abs(self.diferenca)
        self.componentes_pendentes = componentes_pendentes or (
            ComponentePendente(
                "Diferença sem classificação comercial",
                self.diferenca_absoluta,
            ),
        )
        if mensagem is None:
            if self.diferenca > ZERO:
                situacao = (
                    f"faltam distribuir {_moeda(self.diferenca_absoluta)}"
                )
            else:
                situacao = (
                    f"há {_moeda(self.diferenca_absoluta)} a mais nas linhas"
                )
            mensagem = (
                "A composição comercial não fecha: "
                f"{situacao}. Total apresentado: "
                f"{_moeda(self.total_apresentado)}; "
                f"total final: {_moeda(self.total_final)}."
            )
        super().__init__(
            mensagem,
            code="composicao_comercial_invalida",
        )


def validar_fechamento(
    linhas: tuple[LinhaComercial, ...],
    total_final: Decimal,
    *,
    componentes_pendentes: tuple[ComponentePendente, ...] = (),
) -> Decimal:
    """Garante igualdade exata, em centavos, antes de qualquer PDF."""

    total_final = _dinheiro(total_final)
    total_apresentado = _dinheiro(
        sum((linha.valor for linha in linhas), ZERO)
    )
    if total_apresentado != total_final:
        raise ComposicaoComercialInvalida(
            total_apresentado=total_apresentado,
            total_final=total_final,
            componentes_pendentes=componentes_pendentes,
        )
    return total_apresentado


def montar_composicao_comercial(
    orcamento: Orcamento,
    *,
    mostrar_deslocamento: bool,
) -> ComposicaoComercial:
    """Transforma custos internos em preços comerciais consolidados."""

    materiais = _dinheiro(orcamento.subtotal_materiais)
    execucao = _dinheiro(
        orcamento.valor_mao_obra
        + orcamento.subtotal_insumos
        + orcamento.outros_custos_total
        + orcamento.reserva_ferramentas
    )
    deslocamento = _dinheiro(orcamento.custo_deslocamento)
    reserva_empresa = _dinheiro(orcamento.reserva_empresa)
    lucro = _dinheiro(orcamento.lucro_liquido)
    desconto = _dinheiro(orcamento.desconto)
    total_final = _dinheiro(orcamento.total_final)

    if not mostrar_deslocamento:
        execucao = _dinheiro(execucao + deslocamento)
        deslocamento = ZERO

    total_antes_desconto = _dinheiro(
        materiais
        + execucao
        + deslocamento
        + reserva_empresa
        + lucro
    )
    if desconto > total_antes_desconto or total_final < ZERO:
        excesso = max(_dinheiro(desconto - total_antes_desconto), ZERO)
        pendentes = []
        if excesso > ZERO:
            pendentes.append(
                ComponentePendente(
                    "Desconto que excede o valor bruto da proposta",
                    excesso,
                )
            )
        if total_final < ZERO:
            pendentes.append(
                ComponentePendente(
                    "Total final negativo",
                    abs(total_final),
                )
            )
        raise ComposicaoComercialInvalida(
            total_apresentado=max(
                _dinheiro(total_antes_desconto - desconto),
                ZERO,
            ),
            total_final=total_final,
            componentes_pendentes=tuple(pendentes),
            mensagem=(
                "A proposta possui desconto maior que o valor bruto ou "
                "total final negativo. Revise o desconto antes de gerar o PDF."
            ),
        )

    total_componentes = _dinheiro(
        total_antes_desconto - desconto
    )
    if total_componentes != total_final:
        diferenca = abs(_dinheiro(total_final - total_componentes))
        raise ComposicaoComercialInvalida(
            total_apresentado=total_componentes,
            total_final=total_final,
            componentes_pendentes=(
                ComponentePendente(
                    "Diferença entre o resumo interno e o total final",
                    diferenca,
                ),
            ),
        )

    # Materiais e deslocamento mantêm seus valores originais. Todo componente
    # interno que forma o preço de venda fica incorporado comercialmente em
    # "Mão de obra e serviços", sem revelar sua origem ao cliente.
    servicos = _dinheiro(execucao + reserva_empresa + lucro)
    linhas_comerciais = (
        LinhaComercial("servicos", "Mão de obra e serviços", servicos),
        LinhaComercial("materiais", "Materiais fornecidos", materiais),
        LinhaComercial("deslocamento", "Deslocamento", deslocamento),
    )
    linhas = tuple(
        linha for linha in linhas_comerciais if linha.valor > ZERO
    )
    if desconto > ZERO:
        linhas += (
            LinhaComercial("desconto", "Desconto", -desconto),
        )
    if not linhas:
        linhas = (
            LinhaComercial("servicos", "Mão de obra e serviços", ZERO),
        )

    validar_fechamento(linhas, total_final)
    return ComposicaoComercial(linhas=linhas, total_final=total_final)
