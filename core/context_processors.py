from django.conf import settings


def app_context(request):
    database = settings.DATABASES["default"]
    is_postgresql = database["ENGINE"] == "django.db.backends.postgresql"
    database_host = str(database.get("HOST", ""))
    is_neon = is_postgresql and database_host.endswith(".neon.tech")
    return {
        "app_name": "Gestor Elétrico",
        "network_login_required": settings.REQUIRE_LOGIN,
        "database_scope_label": ("Dados na nuvem" if is_postgresql else "Dados locais"),
        "database_backend_label": (
            "Neon PostgreSQL conectado"
            if is_neon
            else ("PostgreSQL conectado" if is_postgresql else "SQLite conectado")
        ),
    }
