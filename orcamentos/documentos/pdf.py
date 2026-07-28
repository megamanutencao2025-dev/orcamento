from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..composicao_comercial import validar_fechamento
from ..models import Orcamento
from .dados import PropostaDados

AZUL = colors.HexColor("#2563EB")
TEXTO = colors.HexColor("#0F172A")
SUAVE = colors.HexColor("#475569")
BORDA = colors.HexColor("#CBD5E1")
FUNDO = colors.HexColor("#F1F5F9")


def _texto_seguro(valor):
    texto = str(valor or "")
    return "".join(
        caractere
        for caractere in texto
        if caractere in "\n\t" or ord(caractere) >= 32
    )


def _paragrafo(valor, estilo):
    texto = escape(_texto_seguro(valor)).replace("\n", "<br/>")
    return Paragraph(texto or "—", estilo)


def _campo_identificacao(rotulo, valor, estilo):
    return Paragraph(
        f"<b>{escape(rotulo)}</b><br/>{escape(_texto_seguro(valor))}",
        estilo,
    )


def _moeda(valor):
    formatado = f"{valor or 0:,.2f}"
    formatado = formatado.replace(",", "#").replace(".", ",").replace("#", ".")
    return f"R$ {formatado}"


def _moeda_linha(valor):
    return f"- {_moeda(abs(valor))}" if valor < 0 else _moeda(valor)


def _quantidade(valor):
    formatado = format(valor, "f").rstrip("0").rstrip(".")
    return (formatado or "0").replace(".", ",")


def _estilos():
    base = getSampleStyleSheet()
    return {
        "normal": ParagraphStyle(
            "PropostaNormal",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=TEXTO,
        ),
        "small": ParagraphStyle(
            "PropostaSmall",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=SUAVE,
        ),
        "company": ParagraphStyle(
            "PropostaCompany",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=TEXTO,
        ),
        "title": ParagraphStyle(
            "PropostaTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=TEXTO,
            spaceAfter=3 * mm,
        ),
        "section": ParagraphStyle(
            "PropostaSection",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=TEXTO,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
        ),
        "right": ParagraphStyle(
            "PropostaRight",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            alignment=TA_RIGHT,
            textColor=TEXTO,
        ),
        "total": ParagraphStyle(
            "PropostaTotal",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            alignment=TA_RIGHT,
            textColor=AZUL,
        ),
        "footer": ParagraphStyle(
            "PropostaFooter",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            alignment=TA_CENTER,
            textColor=SUAVE,
        ),
    }


def _estilo_tabela(*, cabecalho=True):
    comandos = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, BORDA),
    ]
    if cabecalho:
        comandos.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), FUNDO),
                ("TEXTCOLOR", (0, 0), (-1, 0), SUAVE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 7.5),
            ]
        )
    return TableStyle(comandos)


def _desenhar_rodape(canvas, documento, dados, estilos):
    canvas.saveState()
    canvas.setTitle(f"Proposta {dados.numero}")
    canvas.setAuthor(dados.profissional)
    largura, _ = A4
    canvas.setStrokeColor(BORDA)
    canvas.setLineWidth(0.35)
    canvas.line(documento.leftMargin, 14 * mm, largura - documento.rightMargin, 14 * mm)
    rodape = Paragraph(
        f"Proposta {escape(dados.numero)} · Página {documento.page}",
        estilos["footer"],
    )
    rodape.wrapOn(canvas, documento.width, 8 * mm)
    rodape.drawOn(canvas, documento.leftMargin, 7 * mm)
    canvas.restoreState()


def gerar_proposta_pdf(dados: PropostaDados) -> bytes:
    """Gera a proposta do cliente sem informações financeiras internas."""

    validar_fechamento(dados.linhas_valores, dados.total)

    buffer = BytesIO()
    estilos = _estilos()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=16 * mm,
        bottomMargin=20 * mm,
        title=f"Proposta {dados.numero}",
        author=dados.profissional,
    )
    historia = [
        _paragrafo(dados.profissional, estilos["company"]),
    ]
    if dados.contatos_profissional:
        historia.append(
            _paragrafo(
                " | ".join(dados.contatos_profissional),
                estilos["small"],
            )
        )
    historia.extend(
        [
            Spacer(1, 3 * mm),
            HRFlowable(width="100%", thickness=1.1, color=AZUL),
            Spacer(1, 5 * mm),
            Paragraph("PROPOSTA DE ORÇAMENTO", estilos["title"]),
        ]
    )

    identificacao = Table(
        [
            [
                _campo_identificacao(
                    "Orçamento", dados.numero, estilos["normal"]
                ),
                _campo_identificacao(
                    "Data", f"{dados.data:%d/%m/%Y}", estilos["normal"]
                ),
                _campo_identificacao(
                    "Validade",
                    f"{dados.validade:%d/%m/%Y}",
                    estilos["normal"],
                ),
            ]
        ],
        colWidths=[76 * mm, 50 * mm, 50 * mm],
    )
    identificacao.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), FUNDO),
                ("BOX", (0, 0), (-1, -1), 0.5, BORDA),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDA),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    historia.extend(
        [
            identificacao,
            Paragraph("CLIENTE E LOCAL DA OBRA", estilos["section"]),
            _paragrafo(
                "\n".join(
                    parte
                    for parte in (
                        dados.cliente,
                        dados.telefone_cliente,
                        dados.endereco_obra,
                    )
                    if parte
                ),
                estilos["normal"],
            ),
        ]
    )

    if dados.servicos:
        linhas_servicos = [
            [
                _paragrafo("Serviço", estilos["small"]),
                _paragrafo("Quantidade", estilos["small"]),
                _paragrafo("Unidade", estilos["small"]),
            ]
        ]
        linhas_servicos.extend(
            [
                _paragrafo(item.descricao, estilos["normal"]),
                _paragrafo(_quantidade(item.quantidade), estilos["right"]),
                _paragrafo(item.unidade, estilos["normal"]),
            ]
            for item in dados.servicos
        )
        tabela_servicos = LongTable(
            linhas_servicos,
            colWidths=[121 * mm, 30 * mm, 25 * mm],
            repeatRows=1,
        )
        tabela_servicos.setStyle(_estilo_tabela())
        historia.extend(
            [
                Paragraph("SERVIÇOS PREVISTOS", estilos["section"]),
                tabela_servicos,
            ]
        )

    preco_global = (
        dados.modo_apresentacao
        == Orcamento.ModoApresentacao.PRECO_GLOBAL
    )
    if preco_global:
        linhas_materiais_inclusos = [
            [
                _paragrafo("Material incluso", estilos["small"]),
                _paragrafo("Qtd.", estilos["small"]),
                _paragrafo("Unid.", estilos["small"]),
            ]
        ]
        linhas_materiais_inclusos.extend(
            [
                _paragrafo(item.descricao, estilos["normal"]),
                _paragrafo(_quantidade(item.quantidade), estilos["right"]),
                _paragrafo(item.unidade, estilos["normal"]),
            ]
            for item in dados.materiais_inclusos
        )
        if not dados.materiais_inclusos:
            linhas_materiais_inclusos.append(
                [
                    _paragrafo(
                        "Nenhum material fornecido nesta proposta.",
                        estilos["normal"],
                    ),
                    _paragrafo("—", estilos["right"]),
                    _paragrafo("—", estilos["normal"]),
                ]
            )
        tabela_materiais_inclusos = LongTable(
            linhas_materiais_inclusos,
            colWidths=[130 * mm, 23 * mm, 23 * mm],
            repeatRows=1,
        )
        tabela_materiais_inclusos.setStyle(_estilo_tabela())
        historia.extend(
            [
                Paragraph("MATERIAIS INCLUSOS", estilos["section"]),
                tabela_materiais_inclusos,
            ]
        )

    if preco_global:
        linhas_valores = [
            [
                _paragrafo("TOTAL DA PROPOSTA", estilos["normal"]),
                _paragrafo(_moeda(dados.total), estilos["total"]),
            ]
        ]
        titulo_valores = "VALOR GLOBAL"
    else:
        linhas_valores = [
            [
                _paragrafo("Composição da proposta", estilos["small"]),
                _paragrafo("Valor", estilos["small"]),
            ]
        ]
        linhas_valores.extend(
            [
                _paragrafo(linha.descricao, estilos["normal"]),
                _paragrafo(_moeda_linha(linha.valor), estilos["right"]),
            ]
            for linha in dados.linhas_valores
        )
        linhas_valores.append(
            [
                _paragrafo("TOTAL DA PROPOSTA", estilos["normal"]),
                _paragrafo(_moeda(dados.total), estilos["total"]),
            ]
        )
        titulo_valores = "VALORES"

    tabela_valores = Table(linhas_valores, colWidths=[132 * mm, 44 * mm])
    tabela_valores.setStyle(_estilo_tabela(cabecalho=not preco_global))
    tabela_valores.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EFF6FF")),
                ("LINEABOVE", (0, -1), (-1, -1), 1, AZUL),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
                ("TOPPADDING", (0, -1), (-1, -1), 8),
            ]
        )
    )
    historia.extend(
        [
            Paragraph(titulo_valores, estilos["section"]),
            tabela_valores,
            Spacer(1, 1.5 * mm),
            _paragrafo(
                "O total considera todos os custos necessários para a "
                "execução e as condições comerciais desta proposta.",
                estilos["small"],
            ),
        ]
    )

    if dados.materiais_compra:
        linhas_materiais = [
            [
                _paragrafo("Material para compra", estilos["small"]),
                _paragrafo("Qtd.", estilos["small"]),
                _paragrafo("Unid.", estilos["small"]),
                _paragrafo("Observação", estilos["small"]),
            ]
        ]
        linhas_materiais.extend(
            [
                _paragrafo(item.descricao, estilos["normal"]),
                _paragrafo(_quantidade(item.quantidade), estilos["right"]),
                _paragrafo(item.unidade, estilos["normal"]),
                _paragrafo(item.observacao, estilos["normal"]),
            ]
            for item in dados.materiais_compra
        )
        tabela_materiais = LongTable(
            linhas_materiais,
            colWidths=[86 * mm, 21 * mm, 21 * mm, 48 * mm],
            repeatRows=1,
        )
        tabela_materiais.setStyle(_estilo_tabela())
        historia.extend(
            [
                Paragraph(
                    "MATERIAIS PARA O CLIENTE COMPRAR",
                    estilos["section"],
                ),
                tabela_materiais,
            ]
        )

    if dados.observacoes:
        historia.extend(
            [
                Paragraph("OBSERVAÇÕES", estilos["section"]),
                _paragrafo(dados.observacoes, estilos["normal"]),
            ]
        )
    historia.extend(
        [
            Spacer(1, 5 * mm),
            _paragrafo(
                f"Esta proposta é válida até {dados.validade:%d/%m/%Y}.",
                estilos["small"],
            ),
        ]
    )
    documento.build(
        historia,
        onFirstPage=lambda canvas, doc: _desenhar_rodape(
            canvas, doc, dados, estilos
        ),
        onLaterPages=lambda canvas, doc: _desenhar_rodape(
            canvas, doc, dados, estilos
        ),
    )
    return buffer.getvalue()
