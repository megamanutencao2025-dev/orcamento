from django.urls import path

from . import views

app_name = "orcamentos"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.novo, name="novo"),
    path("<int:pk>/", views.detalhe, name="detalhe"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path(
        "<int:pk>/documentos/proposta.pdf",
        views.proposta_pdf,
        name="proposta_pdf",
    ),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
    path("<int:pk>/itens/<str:tipo>/adicionar/", views.adicionar_item, name="adicionar_item"),
    path(
        "<int:pk>/itens/<str:tipo>/<int:item_pk>/remover/",
        views.remover_item,
        name="remover_item",
    ),
]
