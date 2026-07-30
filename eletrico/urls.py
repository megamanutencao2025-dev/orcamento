from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.templatetags.static import static
from django.urls import include, path
from django.views.generic import RedirectView


class FaviconRedirectView(RedirectView):
    """Serve /favicon.ico via staticfiles (hashed path in production)."""

    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        return static("img/favicon.ico")


urlpatterns = [
    path("favicon.ico", FaviconRedirectView.as_view(), name="favicon"),
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
