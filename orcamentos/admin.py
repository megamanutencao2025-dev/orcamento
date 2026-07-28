from django.contrib import admin

from .models import (
    InsumoInterno,
    ItemServico,
    MaterialCliente,
    MaterialFornecido,
    Orcamento,
    OutroCusto,
)

admin.site.register(
    [
        Orcamento,
        MaterialFornecido,
        MaterialCliente,
        InsumoInterno,
        ItemServico,
        OutroCusto,
    ]
)
