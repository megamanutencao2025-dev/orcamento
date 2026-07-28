from django.urls import path

from . import views

app_name = "ferramentas"

urlpatterns = [path("", views.index, name="index")]
