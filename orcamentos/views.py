import json
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from cadastros.models import Dificuldade, Material, Servico, TrabalhoAltura, Veiculo
from core.models import Configuracao

from .composicao_comercial import ComposicaoComercialInvalida
from .documentos import gerar_proposta_pdf, montar_dados_proposta
from .forms import (
    InsumoInternoForm,
    ItemServicoForm,
    MaterialClienteForm,
    MaterialFornecidoForm,
    OrcamentoForm,
    OutroCustoForm,
)
from .models import (
    InsumoInterno,
    ItemServico,
    MaterialCliente,
    MaterialFornecido,
    Orcamento,
    OutroCusto,
)
from .services import calcular_orcamento, salvar_itens_completos


def lista(request):
    queryset = Orcamento.objects.all()
    busca = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if busca:
        queryset = queryset.filter(
            Q(numero__icontains=busca) | Q(cliente_nome__icontains=busca)
        )
    if status:
        queryset = queryset.filter(status=status)
    return render(
        request,
        "orcamentos/lista.html",
        {"orcamentos": queryset, "busca": busca, "status_atual": status},
    )


def _contexto_construtor(
    form, dados_itens, configuracao, *, novo, orcamento=None
):
    materiais = Material.objects.filter(ativo=True).select_related(
        "unidade_medida"
    )
    servicos = Servico.objects.filter(ativo=True)
    veiculos = Veiculo.objects.filter(ativo=True)
    dificuldades = Dificuldade.objects.filter(ativo=True)
    alturas = TrabalhoAltura.objects.filter(ativo=True)
    return {
        "form": form,
        "novo": novo,
        "orcamento": orcamento,
        "configuracao": configuracao,
        "materiais_fornecidos": materiais.filter(
            tipo_uso=Material.TipoUso.FORNECIDO
        ),
        "materiais_referencia": materiais,
        "insumos": materiais.filter(tipo_uso=Material.TipoUso.INSUMO),
        "servicos_catalogo": servicos,
        "veiculos": veiculos,
        "dificuldades": dificuldades,
        "alturas": alturas,
        "dados_catalogos": {
            "materials": [
                {
                    "id": material.pk,
                    "nome": material.nome,
                    "unidade": material.unidade_sigla,
                    "preco_unitario": material.preco_unitario,
                    "fornecedor": material.fornecedor,
                    "tipo_uso": material.tipo_uso,
                }
                for material in materiais
            ],
            "services": list(
                servicos.values("id", "nome", "unidade", "preco_unitario")
            ),
            "vehicles": list(
                veiculos.values(
                    "id", "nome", "km_por_litro", "preco_combustivel"
                )
            ),
            "difficulties": list(
                dificuldades.values("id", "nome", "percentual")
            ),
            "heights": list(alturas.values("id", "nome", "percentual")),
        },
        "dados_itens": dados_itens,
    }


def _serializar_itens(orcamento):
    return {
        "materials": [
            {
                "catalogId": item.material_id,
                "quantity": str(item.quantidade),
                "unit": item.unidade,
                "unitPrice": str(item.preco_unitario),
                "supplier": item.fornecedor,
            }
            for item in orcamento.materiais_fornecidos.order_by("pk")
        ],
        "clientMaterials": [
            {
                "referenceId": item.material_referencia_id,
                "description": item.descricao,
                "quantity": str(item.quantidade),
                "unit": item.unidade,
                "note": item.observacao,
            }
            for item in orcamento.materiais_cliente.order_by("pk")
        ],
        "supplies": [
            {
                "catalogId": item.material_id,
                "quantity": str(item.quantidade),
                "unit": item.unidade,
                "unitPrice": str(item.preco_unitario),
            }
            for item in orcamento.insumos_internos.order_by("pk")
        ],
        "services": [
            {
                "serviceId": item.servico_id,
                "quantity": str(item.quantidade),
                "unitPrice": str(item.preco_unitario),
                "difficultyId": item.dificuldade_id,
                "heightId": item.altura_id,
            }
            for item in orcamento.servicos.order_by("pk")
        ],
        "otherCosts": [
            {
                "description": item.descricao,
                "value": str(item.valor),
            }
            for item in orcamento.outros_custos.order_by("pk")
        ],
    }


def _ler_itens(request):
    try:
        return json.loads(request.POST.get("itens_json", "{}"))
    except json.JSONDecodeError as erro:
        raise ValidationError(
            "Os itens enviados não puderam ser interpretados."
        ) from erro


def novo(request):
    configuracao = Configuracao.carregar()
    dados_itens = {}
    if request.method == "POST":
        form = OrcamentoForm(request.POST)
        formulario_valido = form.is_valid()
        try:
            dados_itens = _ler_itens(request)
            if formulario_valido:
                with transaction.atomic():
                    orcamento = form.save()
                    salvar_itens_completos(orcamento, dados_itens)
        except ValidationError as erro:
            form.add_error(None, erro.messages[0])
        else:
            if formulario_valido:
                messages.success(request, "Orçamento salvo e calculado com sucesso.")
                return redirect("orcamentos:detalhe", pk=orcamento.pk)
    else:
        hoje = timezone.localdate()
        form = OrcamentoForm(
            initial={
                "data": hoje,
                "validade": hoje + timedelta(days=configuracao.validade_padrao_dias),
                "valor_hora": configuracao.valor_hora_padrao,
                "percentual_ferramentas": configuracao.percentual_ferramentas,
                "percentual_empresa": configuracao.percentual_empresa,
                "percentual_lucro": configuracao.percentual_lucro,
                "observacoes_internas": configuracao.observacao_interna_padrao,
                "observacoes_cliente": configuracao.observacao_cliente_padrao,
            }
        )
    return render(
        request,
        "orcamentos/novo.html",
        _contexto_construtor(
            form, dados_itens, configuracao, novo=True
        ),
    )


def editar(request, pk):
    orcamento = get_object_or_404(Orcamento, pk=pk)
    configuracao = Configuracao.carregar()
    dados_itens = {}
    if request.method == "POST":
        form = OrcamentoForm(request.POST, instance=orcamento)
        formulario_valido = form.is_valid()
        try:
            dados_itens = _ler_itens(request)
            if formulario_valido:
                with transaction.atomic():
                    orcamento = form.save()
                    salvar_itens_completos(
                        orcamento, dados_itens, substituir=True
                    )
        except ValidationError as erro:
            form.add_error(None, erro.messages[0])
        else:
            if formulario_valido:
                messages.success(request, "Orçamento atualizado.")
                return redirect("orcamentos:detalhe", pk=orcamento.pk)
    else:
        form = OrcamentoForm(instance=orcamento)
        dados_itens = _serializar_itens(orcamento)
    return render(
        request,
        "orcamentos/novo.html",
        _contexto_construtor(
            form,
            dados_itens,
            configuracao,
            novo=False,
            orcamento=orcamento,
        ),
    )


def detalhe(request, pk):
    orcamento = get_object_or_404(
        Orcamento.objects.select_related("veiculo"), pk=pk
    )
    return render(
        request,
        "orcamentos/detalhe.html",
        {
            "orcamento": orcamento,
            "material_form": MaterialFornecidoForm(prefix="material"),
            "cliente_form": MaterialClienteForm(prefix="cliente"),
            "insumo_form": InsumoInternoForm(prefix="insumo"),
            "servico_form": ItemServicoForm(prefix="servico"),
            "custo_form": OutroCustoForm(prefix="custo"),
        },
    )


def proposta_pdf(request, pk):
    orcamento = get_object_or_404(
        Orcamento.objects.prefetch_related(
            Prefetch(
                "servicos",
                queryset=ItemServico.objects.order_by("pk"),
                to_attr="servicos_proposta",
            ),
            Prefetch(
                "materiais_cliente",
                queryset=MaterialCliente.objects.order_by("pk"),
                to_attr="materiais_compra_proposta",
            ),
            Prefetch(
                "materiais_fornecidos",
                queryset=MaterialFornecido.objects.order_by("pk"),
                to_attr="materiais_inclusos_proposta",
            ),
        ),
        pk=pk,
    )
    configuracao = Configuracao.carregar()
    try:
        dados = montar_dados_proposta(orcamento, configuracao)
        conteudo = gerar_proposta_pdf(dados)
    except ComposicaoComercialInvalida as erro:
        return render(
            request,
            "orcamentos/erro_composicao_pdf.html",
            {
                "orcamento": orcamento,
                "erro_composicao": erro,
                "mensagem_erro": erro.messages[0],
                "componentes_pendentes": erro.componentes_pendentes,
            },
            status=422,
        )
    nome_arquivo = slugify(f"proposta-{orcamento.numero}") + ".pdf"
    modo = "attachment" if request.GET.get("download") == "1" else "inline"
    resposta = HttpResponse(conteudo, content_type="application/pdf")
    resposta["Content-Disposition"] = f'{modo}; filename="{nome_arquivo}"'
    resposta["Cache-Control"] = "private, no-store"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


FORMULARIOS_ITEM = {
    "material": (MaterialFornecidoForm, "material"),
    "cliente": (MaterialClienteForm, "cliente"),
    "insumo": (InsumoInternoForm, "insumo"),
    "servico": (ItemServicoForm, "servico"),
    "custo": (OutroCustoForm, "custo"),
}

MODELOS_ITEM = {
    "material": MaterialFornecido,
    "cliente": MaterialCliente,
    "insumo": InsumoInterno,
    "servico": ItemServico,
    "custo": OutroCusto,
}


@require_POST
def adicionar_item(request, pk, tipo):
    orcamento = get_object_or_404(Orcamento, pk=pk)
    if tipo not in FORMULARIOS_ITEM:
        return redirect("orcamentos:detalhe", pk=pk)
    form_class, prefixo = FORMULARIOS_ITEM[tipo]
    form = form_class(request.POST, prefix=prefixo)
    if form.is_valid():
        try:
            with transaction.atomic():
                item = form.save(commit=False)
                item.orcamento = orcamento
                item.save()
                calcular_orcamento(orcamento)
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
        else:
            messages.success(request, "Item adicionado.")
    else:
        erro = next(iter(form.errors.values()))[0]
        messages.error(request, f"Não foi possível adicionar: {erro}")
    return redirect("orcamentos:detalhe", pk=pk)


@require_POST
def remover_item(request, pk, tipo, item_pk):
    orcamento = get_object_or_404(Orcamento, pk=pk)
    model = MODELOS_ITEM.get(tipo)
    if model:
        try:
            with transaction.atomic():
                item = get_object_or_404(
                    model, pk=item_pk, orcamento=orcamento
                )
                item.delete()
                calcular_orcamento(orcamento)
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
        else:
            messages.success(request, "Item removido.")
    return redirect("orcamentos:detalhe", pk=pk)


@require_POST
def excluir(request, pk):
    orcamento = get_object_or_404(Orcamento, pk=pk)
    numero = orcamento.numero
    orcamento.delete()
    messages.success(request, f"Orçamento {numero} excluído.")
    return redirect("orcamentos:lista")
