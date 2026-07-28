from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path(
        "conta/entrar/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path(
        "conta/sair/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "conta/senha/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
        ),
        name="password_change",
    ),
    path(
        "conta/senha/concluida/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html",
        ),
        name="password_change_done",
    ),
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("cadastros/", include("cadastros.urls")),
    path("orcamentos/", include("orcamentos.urls")),
    path("ferramentas/", include("ferramentas.urls")),
]
