from urllib.parse import parse_qs, unquote, urlsplit


def _parse_neon_url(url, *, pooled):
    parsed = urlsplit(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("A conexão deve usar PostgreSQL.")
    if not parsed.hostname or not parsed.hostname.lower().endswith(".neon.tech"):
        raise ValueError("A conexão deve pertencer ao Neon.")

    hostname = parsed.hostname.lower()
    has_pooler = "-pooler." in hostname
    if pooled and not has_pooler:
        raise ValueError("A conexão de runtime deve conter -pooler.")
    if not pooled and has_pooler:
        raise ValueError("A conexão administrativa deve ser direta.")

    ssl_modes = parse_qs(
        parsed.query,
        keep_blank_values=True,
    ).get("sslmode", [])
    if [value.lower() for value in ssl_modes] != ["require"]:
        raise ValueError("A conexão deve conter exatamente sslmode=require.")

    normalized_host = hostname.replace("-pooler.", ".", 1)
    database = unquote(parsed.path.lstrip("/"))
    username = unquote(parsed.username or "")
    if not database or not username:
        raise ValueError("A conexão não informa banco ou usuário.")
    return normalized_host, database, username


def validate_neon_runtime_url(url):
    """Valida a URL agrupada usada pelo serviço web."""
    _parse_neon_url(url, pooled=True)


def validate_neon_direct_url(url):
    """Valida a URL direta usada por migrations e administração."""
    _parse_neon_url(url, pooled=False)


def validate_neon_connection_pair(runtime_url, direct_url):
    """Confirma que as duas URLs representam o mesmo banco e usuário."""
    runtime_identity = _parse_neon_url(runtime_url, pooled=True)
    direct_identity = _parse_neon_url(direct_url, pooled=False)
    if runtime_identity != direct_identity:
        raise ValueError(
            "As URLs agrupada e direta não apontam para o mesmo "
            "endpoint, banco e usuário."
        )
