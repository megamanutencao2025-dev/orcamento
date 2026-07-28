import json
import logging
from hashlib import sha256

from django.contrib import messages
from django.core.cache import cache
from django.db.models.deletion import ProtectedError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    CategoriaMaterialForm,
    DificuldadeForm,
    MaterialForm,
    ServicoForm,
    TrabalhoAlturaForm,
    UnidadeMedidaForm,
    VeiculoForm,
)
from .models import (
    CategoriaMaterial,
    Dificuldade,
    Material,
    Servico,
    TrabalhoAltura,
    UnidadeMedida,
    Veiculo,
)
from .services.product_import import ProductImportError, import_product

logger = logging.getLogger(__name__)

SECOES = {
    "materiais": (Material, MaterialForm, "Materiais"),
    "categorias": (CategoriaMaterial, CategoriaMaterialForm, "Categorias"),
    "unidades": (UnidadeMedida, UnidadeMedidaForm, "Unidades de medida"),
    "servicos": (Servico, ServicoForm, "Serviços"),
    "veiculos": (Veiculo, VeiculoForm, "Veículos"),
    "dificuldades": (Dificuldade, DificuldadeForm, "Dificuldades"),
    "altura": (TrabalhoAltura, TrabalhoAlturaForm, "Trabalho em altura"),
}


def cadastros(request, secao="materiais"):
    if secao not in SECOES:
        raise Http404
    model, form_class, titulo = SECOES[secao]
    editar = request.GET.get("editar")
    instancia = get_object_or_404(model, pk=editar) if editar else None

    if request.method == "POST":
        form = form_class(request.POST, instance=instancia)
        if form.is_valid():
            item = form.save(commit=False)
            if (
                isinstance(item, Material)
                and item.url_origem
                and (
                    {
                        "url_origem",
                        "preco_compra",
                        "forma_compra",
                        "quantidade_unidades_caixa",
                    }
                    & set(form.changed_data)
                    or not item.importado_em
                )
            ):
                item.importado_em = timezone.now()
            item.save()
            form.save_m2m()
            messages.success(
                request,
                f"{model._meta.verbose_name.capitalize()} salvo com sucesso.",
            )
            return redirect("cadastros:secao", secao=secao)
    else:
        form = form_class(instance=instancia)

    queryset = model.objects.all()
    if model is Material:
        queryset = queryset.select_related("categoria", "unidade_medida")
    return render(
        request,
        "cadastros/index.html",
        {
            "secao": secao,
            "secoes": SECOES,
            "titulo_secao": titulo,
            "form": form,
            "itens": queryset,
            "editando": instancia,
        },
    )


@require_POST
def importar_material_url(request):
    try:
        if request.content_type == "application/json":
            payload = json.loads(request.body or b"{}")
            url = payload.get("url", "")
        else:
            url = request.POST.get("url", "")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"ok": False, "error": "A solicitação enviada é inválida."},
            status=400,
        )

    if not url.strip():
        return JsonResponse(
            {"ok": False, "error": "Informe a URL do produto."},
            status=400,
        )
    cache_key = f"product-preview:{sha256(url.strip().encode()).hexdigest()}"
    cached_product = cache.get(cache_key)
    if cached_product:
        return JsonResponse({"ok": True, "product": cached_product})
    try:
        preview = import_product(url)
    except ProductImportError as error:
        return JsonResponse({"ok": False, "error": str(error)}, status=422)
    except Exception:
        logger.exception("Falha inesperada ao importar produto")
        return JsonResponse(
            {
                "ok": False,
                "error": "Não foi possível analisar esta página agora.",
            },
            status=500,
        )
    product = preview.to_dict()
    cache.set(cache_key, product, timeout=300)
    return JsonResponse({"ok": True, "product": product})


@require_POST
def excluir(request, secao, pk):
    if secao not in SECOES:
        raise Http404
    model, _, titulo = SECOES[secao]
    item = get_object_or_404(model, pk=pk)
    try:
        item.delete()
    except ProtectedError:
        messages.error(
            request,
            "Este item está em uso. Desative-o para manter o histórico.",
        )
    else:
        messages.success(request, f"Item removido de {titulo.lower()}.")
    return redirect("cadastros:secao", secao=secao)
