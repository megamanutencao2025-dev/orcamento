from django.contrib import admin

from .models import (
    CategoriaMaterial,
    Dificuldade,
    Material,
    Servico,
    TrabalhoAltura,
    UnidadeMedida,
    Veiculo,
)

admin.site.register(
    [
        CategoriaMaterial,
        UnidadeMedida,
        Material,
        Servico,
        Veiculo,
        Dificuldade,
        TrabalhoAltura,
    ]
)
