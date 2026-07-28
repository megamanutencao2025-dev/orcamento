"""Importação assistida de produtos publicados em lojas suportadas."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_HTML_BYTES = 3 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 10

SUPPORTED_STORES = {
    "Mercado Livre": (
        "mercadolivre.com.br",
        "mercadolivre.com",
        "mercadolibre.com",
        "meli.la",
    ),
    "Amazon": ("amazon.com.br", "amazon.com", "amzn.to", "a.co"),
    "Shopee": ("shopee.com.br", "shope.ee", "shp.ee"),
    "Eletrorastro": ("eletrorastro.com.br",),
    "Delupo": ("delupo.com.br",),
}


class ProductImportError(Exception):
    """Erro esperado e seguro para exibição na interface."""


class UnsafeProductUrl(ProductImportError):
    """A URL não atende às regras de segurança ou suporte."""


@dataclass
class ProductPreview:
    name: str
    price: Decimal | None
    image_url: str
    supplier: str
    source_url: str
    source: str
    currency: str = "BRL"
    confidence: str = "medium"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        data = asdict(self)
        data["price"] = f"{self.price:.2f}" if self.price is not None else None
        return data


def _domain_matches(hostname: str, domain: str) -> bool:
    return hostname == domain or hostname.endswith(f".{domain}")


def identify_store(hostname: str) -> str | None:
    hostname = hostname.lower().rstrip(".")
    for store, domains in SUPPORTED_STORES.items():
        if any(_domain_matches(hostname, domain) for domain in domains):
            return store
    return None


def _reject_non_public_addresses(hostname: str):
    try:
        addresses = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise ProductImportError(
            "Não foi possível localizar o endereço informado."
        ) from error

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UnsafeProductUrl("O endereço informado não é público.")


def validate_product_url(url: str, *, resolve_dns: bool = True) -> tuple[str, str]:
    value = (url or "").strip()
    if len(value) > 2000:
        raise UnsafeProductUrl("A URL é muito longa.")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeProductUrl("Use uma URL iniciada por http:// ou https://.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeProductUrl("A URL informada é inválida.")
    try:
        port = parsed.port
    except ValueError:
        raise UnsafeProductUrl("A porta informada é inválida.") from None
    if port not in {None, 80, 443}:
        raise UnsafeProductUrl("Apenas portas HTTP e HTTPS são permitidas.")

    hostname = parsed.hostname.lower().rstrip(".")
    store = identify_store(hostname)
    if not store:
        supported = ", ".join(SUPPORTED_STORES)
        raise UnsafeProductUrl(
            f"Loja ainda não suportada. Use uma URL de: {supported}."
        )
    if resolve_dns:
        _reject_non_public_addresses(hostname)
    return value, store


class SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        absolute_url = urljoin(req.full_url, newurl)
        validate_product_url(absolute_url)
        return super().redirect_request(
            req, fp, code, msg, headers, absolute_url
        )


def fetch_product_html(url: str) -> tuple[str, str, str]:
    safe_url, store = validate_product_url(url)
    request = Request(
        safe_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/124 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.6",
            "Accept-Encoding": "identity",
        },
    )
    opener = build_opener(SafeRedirectHandler())
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            final_url = response.geturl()
            validate_product_url(final_url)
            content_type = response.headers.get_content_type()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise ProductImportError("A URL não retornou uma página de produto.")
            raw = response.read(MAX_HTML_BYTES + 1)
            if len(raw) > MAX_HTML_BYTES:
                raise ProductImportError("A página retornada é muito grande.")
            charset = response.headers.get_content_charset() or "utf-8"
    except HTTPError as error:
        if error.code in {401, 403, 429}:
            raise ProductImportError(
                "A loja bloqueou a consulta automática. Preencha os dados manualmente."
            ) from error
        raise ProductImportError(
            f"A loja respondeu com o erro HTTP {error.code}."
        ) from error
    except (TimeoutError, socket.timeout):
        raise ProductImportError("A loja demorou demais para responder.") from None
    except URLError as error:
        raise ProductImportError(
            "Não foi possível acessar a página do produto."
        ) from error

    return raw.decode(charset, errors="replace"), final_url, store


class ProductMetadataParser(HTMLParser):
    VOID_TAGS = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
    CAPTURE_CLASSES = {
        "a-offscreen": "amazon_offscreen",
        "a-price-whole": "amazon_whole",
        "a-price-fraction": "amazon_fraction",
        "andes-money-amount__fraction": "meli_whole",
        "andes-money-amount__cents": "meli_fraction",
        "vtex-product-price-1-x-sellingpricevalue": "vtex_price",
        "preco-por": "store_price",
        "precopor": "store_price",
        "preco-venda": "store_price",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.meta: dict[str, list[str]] = {}
        self.captures: dict[str, list[str]] = {}
        self.active: list[dict[str, Any]] = []
        self.json_ld: list[str] = []
        self._script_parts: list[str] | None = None
        self.title = ""
        self._title_parts: list[str] | None = None

    def _add_meta(self, key: str, value: str):
        if key and value:
            self.meta.setdefault(key.lower(), []).append(value.strip())

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attributes = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            key = (
                attributes.get("property")
                or attributes.get("name")
                or attributes.get("itemprop")
            )
            self._add_meta(key, attributes.get("content", ""))
        elif tag == "link":
            key = attributes.get("itemprop") or attributes.get("rel")
            self._add_meta(key, attributes.get("href", ""))
        elif tag == "img" and attributes.get("id", "").lower() == "landingimage":
            image = (
                attributes.get("data-old-hires")
                or attributes.get("src")
                or attributes.get("data-src")
            )
            if not image and attributes.get("data-a-dynamic-image"):
                try:
                    image = next(
                        iter(json.loads(attributes["data-a-dynamic-image"]))
                    )
                except (json.JSONDecodeError, StopIteration, TypeError):
                    image = ""
            self._add_meta("amazon:landing-image", image)

        if tag == "script" and "ld+json" in attributes.get("type", "").lower():
            self._script_parts = []
        if tag == "title":
            self._title_parts = []

        if tag in self.VOID_TAGS:
            return
        self.depth += 1
        capture_keys = []
        if tag == "h1":
            capture_keys.append("h1")
        if attributes.get("id", "").lower() == "producttitle":
            capture_keys.append("product_title")
        classes = set(attributes.get("class", "").lower().split())
        capture_keys.extend(
            capture
            for css_class, capture in self.CAPTURE_CLASSES.items()
            if css_class in classes
        )
        for key in capture_keys:
            self.active.append({"depth": self.depth, "key": key, "parts": []})

    def handle_data(self, data):
        if self._script_parts is not None:
            self._script_parts.append(data)
        if self._title_parts is not None:
            self._title_parts.append(data)
        for capture in self.active:
            capture["parts"].append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "script" and self._script_parts is not None:
            value = "".join(self._script_parts).strip()
            if value:
                self.json_ld.append(value)
            self._script_parts = None
        if tag == "title" and self._title_parts is not None:
            self.title = _clean_text("".join(self._title_parts))
            self._title_parts = None
        if tag in self.VOID_TAGS:
            return
        ending = [item for item in self.active if item["depth"] == self.depth]
        for item in ending:
            value = _clean_text("".join(item["parts"]))
            if value:
                self.captures.setdefault(item["key"], []).append(value)
            self.active.remove(item)
        self.depth = max(0, self.depth - 1)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def _first(mapping: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        values = mapping.get(key.lower(), [])
        if values and values[0]:
            return _clean_text(values[0])
    return ""


def _parse_price(value: Any) -> Decimal | None:
    if isinstance(value, (int, float, Decimal)):
        try:
            parsed = Decimal(str(value))
            return parsed.quantize(Decimal("0.01")) if parsed.is_finite() else None
        except InvalidOperation:
            return None
    text = _clean_text(value)
    match = re.search(r"(\d[\d.\s]*,\d{1,2}|\d[\d,\s]*\.\d{1,2}|\d[\d.\s]*)", text)
    if not match:
        return None
    numeric = match.group(1).replace(" ", "")
    if "," in numeric and "." in numeric:
        if numeric.rfind(",") > numeric.rfind("."):
            numeric = numeric.replace(".", "").replace(",", ".")
        else:
            numeric = numeric.replace(",", "")
    elif "," in numeric:
        numeric = numeric.replace(".", "").replace(",", ".")
    elif numeric.count(".") > 1:
        numeric = numeric.replace(".", "")
    try:
        result = Decimal(numeric)
    except InvalidOperation:
        return None
    return result.quantize(Decimal("0.01")) if result.is_finite() else None


def _walk_json(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _is_type(node: dict, expected: str) -> bool:
    types = node.get("@type", [])
    if isinstance(types, str):
        types = [types]
    return any(str(value).rsplit("/", 1)[-1].lower() == expected.lower() for value in types)


def _image_value(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return next((_image_value(item) for item in value if _image_value(item)), "")
    if isinstance(value, dict):
        return value.get("url") or value.get("contentUrl") or ""
    return ""


def _offer_data(value) -> tuple[Decimal | None, str, bool]:
    offers = value if isinstance(value, list) else [value]
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        raw_price = offer.get("price") or offer.get("lowPrice")
        specification = offer.get("priceSpecification")
        if raw_price is None and isinstance(specification, dict):
            raw_price = specification.get("price")
        price = _parse_price(raw_price)
        if price is not None:
            high = _parse_price(offer.get("highPrice"))
            is_range = high is not None and high != price
            currency = (
                offer.get("priceCurrency")
                or (specification or {}).get("priceCurrency")
                if isinstance(specification, dict)
                else offer.get("priceCurrency")
            )
            return price, currency or "BRL", is_range
    return None, "BRL", False


def _json_ld_product(scripts: list[str]) -> dict[str, Any]:
    candidates = []
    for script in scripts:
        try:
            parsed = json.loads(script)
        except (json.JSONDecodeError, TypeError):
            continue
        for node in _walk_json(parsed):
            if isinstance(node, dict) and _is_type(node, "Product"):
                price, currency, is_range = _offer_data(node.get("offers", []))
                candidates.append(
                    {
                        "name": _clean_text(node.get("name")),
                        "price": price,
                        "currency": currency,
                        "image": _image_value(node.get("image")),
                        "range": is_range,
                    }
                )
    if not candidates:
        return {}
    return max(
        candidates,
        key=lambda item: sum(bool(item.get(key)) for key in ("name", "price", "image")),
    )


def _safe_image_url(value: str, base_url: str) -> str:
    if not value:
        return ""
    absolute = urljoin(base_url, value)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    try:
        ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return absolute
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        return ""
    return absolute


def _store_price(parser: ProductMetadataParser, store: str) -> Decimal | None:
    if store == "Amazon":
        for value in parser.captures.get("amazon_offscreen", []):
            price = _parse_price(value)
            if price is not None:
                return price
        whole = _first(parser.captures, "amazon_whole")
        fraction = _first(parser.captures, "amazon_fraction")
        if whole:
            return _parse_price(f"{whole},{fraction or '00'}")
    if store == "Mercado Livre":
        whole = _first(parser.captures, "meli_whole")
        fraction = _first(parser.captures, "meli_fraction")
        if whole:
            return _parse_price(f"{whole},{fraction or '00'}")
    for key in ("vtex_price", "store_price"):
        for value in parser.captures.get(key, []):
            price = _parse_price(value)
            if price is not None:
                return price
    return None


def _strip_store_suffix(name: str, store: str) -> str:
    suffixes = {
        "Mercado Livre": (r"\s*\|\s*Mercado\s*Livre.*$",),
        "Amazon": (r"\s*[:|]\s*Amazon\.com\.br.*$",),
        "Shopee": (r"\s*[-|]\s*Shopee Brasil.*$",),
        "Eletrorastro": (r"\s*\|\s*Eletrorastro.*$",),
        "Delupo": (r"\s*[-|]\s*Delupo.*$",),
    }
    result = name
    for pattern in suffixes.get(store, ()):
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    return result.strip()


def extract_product(html: str, final_url: str, store: str) -> ProductPreview:
    parser = ProductMetadataParser()
    parser.feed(html)
    structured = _json_ld_product(parser.json_ld)

    name = (
        structured.get("name")
        or _first(parser.meta, "og:title", "twitter:title", "name")
        or _first(parser.captures, "product_title", "h1")
        or parser.title
    )
    name = _strip_store_suffix(_clean_text(name), store)
    if not name:
        raise ProductImportError(
            "Não foi possível identificar o nome do produto nesta página."
        )

    price = structured.get("price")
    price_source = "dados estruturados"
    if price is None:
        price = _parse_price(
            _first(
                parser.meta,
                "product:price:amount",
                "og:price:amount",
                "product:price",
                "price",
            )
        )
        price_source = "metadados da página"
    if price is None:
        price = _store_price(parser, store)
        price_source = "página da loja"

    image = (
        structured.get("image")
        or _first(
            parser.meta,
            "og:image:secure_url",
            "og:image",
            "twitter:image",
            "amazon:landing-image",
            "image",
            "image_src",
        )
    )
    image = _safe_image_url(image, final_url)
    warnings = []
    if price is None:
        warnings.append(
            "O preço não foi encontrado automaticamente; informe-o antes de salvar."
        )
    if not image:
        warnings.append("A página não forneceu uma imagem utilizável.")
    if structured.get("range"):
        warnings.append(
            "O anúncio possui variações de preço; foi usado o menor valor publicado."
        )

    confidence = "high" if structured.get("name") and price is not None else "medium"
    if price is None:
        confidence = "low"
    return ProductPreview(
        name=name[:160],
        price=price,
        image_url=image,
        supplier=store,
        source_url=final_url,
        source=price_source,
        currency=structured.get("currency") or _first(
            parser.meta, "product:price:currency", "pricecurrency"
        )
        or "BRL",
        confidence=confidence,
        warnings=warnings,
    )


def import_product(url: str) -> ProductPreview:
    safe_url, store = validate_product_url(url)
    if store == "Delupo":
        try:
            return _import_delupo_vtex(safe_url)
        except ProductImportError:
            pass

    html, final_url, store = fetch_product_html(safe_url)
    blocked = any(
        marker in final_url.lower()
        for marker in (
            "/account-verification",
            "/captcha",
            "/challenge",
        )
    )
    try:
        preview = extract_product(html, final_url, store)
        if blocked or (
            store == "Mercado Livre"
            and preview.name.lower() in {"mercado libre", "mercado livre"}
        ):
            raise ProductImportError("A loja solicitou verificação.")
        return preview
    except ProductImportError:
        fallback_name = _name_from_url(safe_url, store)
        if not fallback_name:
            raise
        return ProductPreview(
            name=fallback_name[:160],
            price=None,
            image_url="",
            supplier=store,
            source_url=safe_url,
            source="endereço do produto",
            confidence="low",
            warnings=[
                (
                    f"A {store} protegeu os detalhes desta página. "
                    "Confira nome e preencha preço e imagem manualmente."
                )
            ],
        )


def _name_from_url(url: str, store: str) -> str:
    path = unquote(urlparse(url).path).strip("/")
    if not path:
        return ""
    if store == "Mercado Livre":
        listing = re.search(r"MLB-\d+-(.+?)-_JM", path, re.IGNORECASE)
        if listing:
            slug = listing.group(1)
        elif "/p/" in f"/{path}/":
            slug = path.split("/p/", 1)[0].rsplit("/", 1)[-1]
        else:
            slug = path.rsplit("/", 1)[-1]
    elif store == "Shopee":
        slug = path.rsplit("/", 1)[-1].split("-i.", 1)[0]
    elif store == "Amazon" and "/dp/" in f"/{path}/":
        slug = path.split("/dp/", 1)[0].rsplit("/", 1)[-1]
    elif store == "Delupo" and path.endswith("/p"):
        slug = path[:-2].rstrip("/").rsplit("/", 1)[-1]
    else:
        slug = path.rsplit("/", 1)[-1]
    slug = re.sub(r"[-_]+", " ", slug)
    return _clean_text(slug).title()


def _fetch_json(url: str):
    validate_product_url(url)
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 GestorEletrico/1.0",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        },
    )
    try:
        with build_opener(SafeRedirectHandler()).open(
            request, timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:
            if response.headers.get_content_type() != "application/json":
                raise ProductImportError("O catálogo da loja não retornou JSON.")
            raw = response.read(MAX_HTML_BYTES + 1)
            if len(raw) > MAX_HTML_BYTES:
                raise ProductImportError("A resposta do catálogo é muito grande.")
    except (HTTPError, URLError, TimeoutError, socket.timeout) as error:
        raise ProductImportError(
            "Não foi possível consultar o catálogo da loja."
        ) from error
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ProductImportError("O catálogo retornou dados inválidos.") from error


def _import_delupo_vtex(url: str) -> ProductPreview:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path.endswith("/p"):
        raise ProductImportError("A URL não parece ser de um produto da Delupo.")
    slug = path[:-2].strip("/").rsplit("/", 1)[-1]
    api_url = (
        f"{parsed.scheme}://{parsed.netloc}"
        f"/api/catalog_system/pub/products/search/{slug}/p"
    )
    products = _fetch_json(api_url)
    if not isinstance(products, list) or not products:
        raise ProductImportError("Produto não encontrado no catálogo da Delupo.")
    product = products[0]
    items = product.get("items") or []
    prices = []
    image = ""
    for item in items:
        if not image and item.get("images"):
            image = item["images"][0].get("imageUrl", "")
        for seller in item.get("sellers") or []:
            offer = seller.get("commertialOffer") or {}
            price = _parse_price(offer.get("Price"))
            if price is not None and price > 0 and offer.get("IsAvailable", True):
                prices.append(price)
    warnings = []
    if len(set(prices)) > 1:
        warnings.append(
            "O produto possui variações; foi usado o menor preço disponível."
        )
    price = min(prices) if prices else None
    if price is None:
        warnings.append(
            "O preço não foi encontrado automaticamente; informe-o antes de salvar."
        )
    return ProductPreview(
        name=_clean_text(
            product.get("productName") or product.get("productTitle")
        )[:160],
        price=price,
        image_url=_safe_image_url(image, url),
        supplier="Delupo",
        source_url=url,
        source="catálogo da loja",
        confidence="high" if price is not None else "medium",
        warnings=warnings,
    )
