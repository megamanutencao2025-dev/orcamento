from django.urls import path

from . import views

app_name = "cadastros"

urlpatterns = [
    path("", views.cadastros, name="index"),
    path(
        "materiais/importar-url/",
        views.importar_material_url,
        name="importar_material_url",
    ),
    path("<str:secao>/", views.cadastros, name="secao"),
    path("<str:secao>/<int:pk>/excluir/", views.excluir, name="excluir"),
]
