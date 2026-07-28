from django.shortcuts import render

from .models import AnaliseProdutividade


def index(request):
    return render(
        request,
        "ferramentas/index.html",
        {"analises": AnaliseProdutividade.objects.prefetch_related("itens")},
    )
