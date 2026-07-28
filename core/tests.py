import json
import os
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from cadastros.models import CategoriaMaterial
from eletrico.database_urls import validate_neon_connection_pair
from eletrico.settings import _env_bool

NETWORK_MIDDLEWARE = list(settings.MIDDLEWARE)
authentication_index = NETWORK_MIDDLEWARE.index(
    "django.contrib.auth.middleware.AuthenticationMiddleware"
)
NETWORK_MIDDLEWARE.insert(
    authentication_index + 1,
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
)

NEON_RUNTIME_URL = (
    "postgresql://gestor:senha@"
    "ep-exemplo-pooler.us-east-1.aws.neon.tech/gestor"
    "?sslmode=require"
)
NEON_DIRECT_URL = (
    "postgresql://gestor:senha@"
    "ep-exemplo.us-east-1.aws.neon.tech/gestor"
    "?sslmode=require"
)


class NeonDatabaseUrlTests(TestCase):
    def test_par_agrupado_e_direto_compativel(self):
        validate_neon_connection_pair(
            NEON_RUNTIME_URL,
            NEON_DIRECT_URL,
        )

    def test_par_de_endpoints_diferentes_e_rejeitado(self):
        other_direct_url = NEON_DIRECT_URL.replace(
            "ep-exemplo.",
            "ep-outro.",
        )

        with self.assertRaises(ValueError):
            validate_neon_connection_pair(
                NEON_RUNTIME_URL,
                other_direct_url,
            )

    def test_sslmode_duplicado_e_rejeitado(self):
        invalid_url = NEON_DIRECT_URL + "&sslmode=disable"

        with self.assertRaises(ValueError):
            validate_neon_connection_pair(
                NEON_RUNTIME_URL,
                invalid_url,
            )


class ConfiguracaoRedeTests(TestCase):
    def test_health_check_retorna_aplicacao_e_banco_disponiveis(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "database": "available"},
        )

    @override_settings(
        ALLOWED_HOSTS=[
            "localhost",
            "192.168.0.34",
            "100.118.116.94",
        ]
    )
    def test_hosts_lan_e_tailscale_aceitam_porta(self):
        for host in ("192.168.0.34:8010", "100.118.116.94:8010"):
            with self.subTest(host=host):
                response = self.client.get("/", HTTP_HOST=host)
                self.assertEqual(response.status_code, 200)

    @override_settings(ALLOWED_HOSTS=["localhost"])
    def test_host_nao_configurado_e_rejeitado(self):
        response = self.client.get("/", HTTP_HOST="203.0.113.10:8010")

        self.assertEqual(response.status_code, 400)

    @override_settings(
        ALLOWED_HOSTS=["192.168.0.34"],
        CSRF_TRUSTED_ORIGINS=["http://192.168.0.34:8010"],
    )
    def test_post_com_csrf_funciona_pelo_endereco_lan(self):
        client = Client(enforce_csrf_checks=True)
        host = "192.168.0.34:8010"
        origin = f"http://{host}"
        client.get("/cadastros/categorias/", HTTP_HOST=host)
        csrf_token = client.cookies["csrftoken"].value

        response = client.post(
            "/cadastros/categorias/",
            {
                "csrfmiddlewaretoken": csrf_token,
                "nome": "Categoria via rede",
                "descricao": "",
            },
            HTTP_HOST=host,
            HTTP_ORIGIN=origin,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CategoriaMaterial.objects.filter(nome="Categoria via rede").exists()
        )

    def test_variavel_booleana_invalida_e_rejeitada(self):
        with patch.dict(os.environ, {"REDE_TESTE_BOOL": "talvez"}):
            with self.assertRaises(ImproperlyConfigured):
                _env_bool("REDE_TESTE_BOOL")


@override_settings(
    MIDDLEWARE=NETWORK_MIDDLEWARE,
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    REQUIRE_LOGIN=True,
)
class AutenticacaoRedeTests(TestCase):
    def setUp(self):
        self.password = "RedeLocal!2026-Protegida"
        self.user = get_user_model().objects.create_user(
            username="eletricista",
            password=self.password,
        )

    def test_visitante_e_redirecionado_para_login(self):
        response = self.client.get("/")

        self.assertRedirects(
            response,
            f"{reverse('login')}?next=/",
            fetch_redirect_response=False,
        )

    def test_login_e_admin_login_permanecem_publicos(self):
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)
        self.assertEqual(self.client.get("/admin/login/").status_code, 200)

    def test_health_check_permanece_publico(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "database": "available"},
        )

    def test_post_anonimo_nao_altera_dados(self):
        response = self.client.post(
            "/cadastros/categorias/",
            {"nome": "Não deve existir", "descricao": ""},
        )

        self.assertRedirects(
            response,
            f"{reverse('login')}?next=/cadastros/categorias/",
            fetch_redirect_response=False,
        )
        self.assertFalse(
            CategoriaMaterial.objects.filter(nome="Não deve existir").exists()
        )

    def test_login_libera_acesso_e_preserva_destino(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": self.user.username,
                "password": self.password,
                "next": reverse("orcamentos:novo"),
            },
        )

        self.assertRedirects(
            response,
            reverse("orcamentos:novo"),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            self.client.get(reverse("orcamentos:novo")).status_code,
            200,
        )

    def test_login_invalido_e_usuario_inativo_nao_autenticam(self):
        invalid_response = self.client.post(
            reverse("login"),
            {
                "username": self.user.username,
                "password": "senha-incorreta",
            },
        )
        self.assertEqual(invalid_response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

        self.user.is_active = False
        self.user.save(update_fields={"is_active"})
        inactive_response = self.client.post(
            reverse("login"),
            {
                "username": self.user.username,
                "password": self.password,
            },
        )
        self.assertEqual(inactive_response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_nao_redireciona_para_dominio_externo(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": self.user.username,
                "password": self.password,
                "next": "https://host-malicioso.invalid/",
            },
        )

        self.assertRedirects(
            response,
            reverse("core:dashboard"),
            fetch_redirect_response=False,
        )

    def test_logout_usa_post_e_bloqueia_novamente(self):
        self.client.force_login(self.user)

        self.assertEqual(
            self.client.get(reverse("logout")).status_code,
            405,
        )
        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))
        self.assertRedirects(
            self.client.get("/"),
            f"{reverse('login')}?next=/",
            fetch_redirect_response=False,
        )

    def test_logout_exige_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)

        self.assertEqual(client.post(reverse("logout")).status_code, 403)

        client.get("/")
        csrf_token = client.cookies["csrftoken"].value
        response = client.post(
            reverse("logout"),
            {"csrfmiddlewaretoken": csrf_token},
        )
        self.assertRedirects(response, reverse("login"))

    def test_usuario_pode_alterar_a_senha(self):
        self.client.force_login(self.user)
        new_password = "NovaSenha!2026-BemProtegida"

        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": self.password,
                "new_password1": new_password,
                "new_password2": new_password,
            },
        )

        self.assertRedirects(
            response,
            reverse("password_change_done"),
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class EnsureNetworkAdminCommandTests(TestCase):
    def test_check_falha_sem_administrador(self):
        with self.assertRaises(CommandError):
            call_command("ensure_network_admin", "--check")

    def test_modo_ambiente_exige_senha_quando_banco_esta_vazio(self):
        with patch.dict(
            os.environ,
            {
                "DJANGO_SUPERUSER_USERNAME": "admin",
                "DJANGO_SUPERUSER_EMAIL": "",
                "DJANGO_SUPERUSER_PASSWORD": "",
            },
        ):
            with self.assertRaises(CommandError):
                call_command(
                    "ensure_network_admin",
                    "--from-environment",
                )

    def test_modo_ambiente_cria_administrador_sem_expor_senha(self):
        output = StringIO()
        password = "RenderNeon!2026-Segura"

        with patch.dict(
            os.environ,
            {
                "DJANGO_SUPERUSER_USERNAME": "admin-cloud",
                "DJANGO_SUPERUSER_EMAIL": "admin@example.com",
                "DJANGO_SUPERUSER_PASSWORD": password,
            },
        ):
            call_command(
                "ensure_network_admin",
                "--from-environment",
                stdout=output,
            )

        administrator = get_user_model().objects.get(username="admin-cloud")
        self.assertTrue(administrator.is_superuser)
        self.assertTrue(administrator.check_password(password))
        self.assertNotIn(password, output.getvalue())

    @patch(
        "core.management.commands.ensure_network_admin.sys.stdin.isatty",
        return_value=True,
    )
    @patch(
        "core.management.commands.ensure_network_admin.getpass",
        side_effect=[
            "RedeLocal!2026-Protegida",
            "RedeLocal!2026-Protegida",
        ],
    )
    @patch(
        "builtins.input",
        side_effect=["administrador", "admin@example.com"],
    )
    def test_cria_primeiro_administrador_sem_expor_senha(
        self,
        _input,
        _getpass,
        _isatty,
    ):
        output = StringIO()

        call_command("ensure_network_admin", stdout=output)

        administrator = get_user_model().objects.get(username="administrador")
        self.assertTrue(administrator.is_active)
        self.assertTrue(administrator.is_staff)
        self.assertTrue(administrator.is_superuser)
        self.assertTrue(administrator.check_password("RedeLocal!2026-Protegida"))
        self.assertNotIn("RedeLocal!2026-Protegida", output.getvalue())
        call_command("ensure_network_admin", "--check")


class DeploymentDataCommandsTests(TestCase):
    def test_preflight_neon_rejeita_banco_que_nao_e_postgresql(self):
        with self.assertRaises(CommandError):
            call_command("assert_neon_pristine_database")

    def test_integridade_da_origem_sqlite(self):
        output = StringIO()

        call_command("check_sqlite_source", stdout=output)

        self.assertIn("SQLite", output.getvalue())

    def test_destino_vazio_com_unidades_padrao_e_aceito_em_teste(self):
        output = StringIO()

        call_command(
            "assert_neon_import_target",
            "--allow-non-postgres",
            stdout=output,
        )

        self.assertIn("compatível", output.getvalue())

    def test_destino_com_dado_de_negocio_e_rejeitado(self):
        CategoriaMaterial.objects.create(nome="Destino ocupado")

        with self.assertRaises(CommandError):
            call_command(
                "assert_neon_import_target",
                "--allow-non-postgres",
            )

    def test_retrato_inclui_contagens_usuario_e_totais(self):
        get_user_model().objects.create_superuser(
            username="snapshot-admin",
            password="Snapshot!2026-Segura",
        )
        output = StringIO()

        call_command("deployment_data_snapshot", stdout=output)
        snapshot = json.loads(output.getvalue())

        self.assertEqual(snapshot["counts"]["auth.User"], 1)
        self.assertTrue(snapshot["users"][0]["usable_password"])
        self.assertEqual(snapshot["quotes"], [])
