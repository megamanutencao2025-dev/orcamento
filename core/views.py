from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.db import DatabaseError, connection
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render

from orcamentos.models import Orcamento

from .forms import ConfiguracaoForm
from .models import Configuracao


@login_not_required
def health(request):
    """Confirma que a aplicação e sua conexão principal estão disponíveis."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse(
            {"status": "error", "database": "unavailable"},
            status=503,
        )
    return JsonResponse({"status": "ok", "database": "available"})


def dashboard(request):
    orcamentos = Orcamento.objects.order_by("-criado_em")
    contexto = {
        "total_orcamentos": orcamentos.count(),
        "orcamentos_abertos": orcamentos.filter(
            status__in=[Orcamento.Status.RASCUNHO, Orcamento.Status.ENVIADO]
        ).count(),
        "orcamentos_aprovados": orcamentos.filter(
            status=Orcamento.Status.APROVADO
        ).count(),
        "valor_aprovado": orcamentos.filter(status=Orcamento.Status.APROVADO).aggregate(
            total=Sum("total_final")
        )["total"]
        or 0,
        "recentes": orcamentos[:5],
    }
    return render(request, "core/dashboard.html", contexto)


def configuracoes(request):
    configuracao = Configuracao.carregar()
    if request.method == "POST":
        form = ConfiguracaoForm(request.POST, instance=configuracao)
        if form.is_valid():
            form.save()
            messages.success(request, "Configurações atualizadas.")
            return redirect("core:configuracoes")
    else:
        form = ConfiguracaoForm(instance=configuracao)
    return render(request, "core/configuracoes.html", {"form": form})
