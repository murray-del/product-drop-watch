import html
import os
import smtplib
import urllib.request
import json
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

LISTING_TZ = ZoneInfo("America/New_York")

STORE_NAME = os.environ.get("STORE_DISPLAY_NAME", "the shop")
STORE_BASE_URL = os.environ["STORE_BASE_URL"]
STORE_PLATFORM = os.environ.get("STORE_PLATFORM", "bigcartel")
CATEGORY_PRIORITY = [h.strip() for h in os.environ.get("CATEGORY_PRIORITY", "").split(",") if h.strip()]
PRODUCTS_URL = STORE_BASE_URL + "/products.json"

GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "murray@murrayabeles.com")


def _fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "product-watch/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _tiered_position(product_categories, native_position):
    """tier by first matching CATEGORY_PRIORITY permalink (else last), broken
    within a tier by the store's own native position."""
    permalinks = {c["permalink"] for c in product_categories}
    tier = next((i for i, h in enumerate(CATEGORY_PRIORITY) if h in permalinks), len(CATEGORY_PRIORITY))
    return tier * 1_000_000 + native_position


def _fetch_bigcartel_products():
    data = _fetch_json(PRODUCTS_URL)
    if not CATEGORY_PRIORITY:
        return data
    for p in data:
        p["position"] = _tiered_position(p.get("categories") or [], p["position"])
    return data


def _shopify_category_positions():
    """Rank id -> flattened position based on CATEGORY_PRIORITY: products in the
    first listed collection sort first (in that collection's own order), then
    the next collection, etc. Products in none of the priority collections sort
    last, in the order the main product feed returns them."""
    positions = {}
    tier_size = 1_000_000
    for tier, handle in enumerate(CATEGORY_PRIORITY):
        data = _fetch_json(STORE_BASE_URL + f"/collections/{handle}/products.json?limit=250")
        for index, p in enumerate(data["products"]):
            positions.setdefault(p["id"], tier * tier_size + index)
    return positions


def _fetch_shopify_products():
    data = _fetch_json(STORE_BASE_URL + "/products.json?limit=250")
    category_positions = _shopify_category_positions() if CATEGORY_PRIORITY else {}
    fallback_tier = len(CATEGORY_PRIORITY) * 1_000_000

    normalized = []
    for index, p in enumerate(data["products"]):
        variants = p.get("variants") or []
        prices = [float(v["price"]) for v in variants if v.get("price") is not None]
        available = any(v.get("available") for v in variants)
        position = category_positions.get(p["id"], fallback_tier + index) if CATEGORY_PRIORITY else None
        normalized.append(
            {
                "id": p["id"],
                "name": p["title"],
                "price": min(prices) if prices else None,
                "status": "active" if available else "sold-out",
                "created_at": p["created_at"],
                "url": f"/products/{p['handle']}",
                "images": [{"url": img["src"]} for img in (p.get("images") or [])],
                "position": position,
            }
        )
    return normalized


def fetch_products():
    if STORE_PLATFORM == "shopify":
        return _fetch_shopify_products()
    return _fetch_bigcartel_products()


def send_email(subject, text_body, html_body=None):
    if html_body is None:
        msg = MIMEText(text_body)
    else:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = NOTIFY_EMAIL
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [NOTIFY_EMAIL], msg.as_string())


def listed_at(product):
    dt = datetime.fromisoformat(product["created_at"].replace("Z", "+00:00"))
    local = dt.astimezone(LISTING_TZ)
    return local.strftime("%b %d, %Y"), local.strftime("%-I:%M %p %Z")


def format_duration(minutes):
    total_seconds = int(minutes * 60)
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins or not parts:
        parts.append(f"{mins}m")
    return " ".join(parts)


def product_url(product):
    return STORE_BASE_URL + product["url"]


def product_image(product):
    images = product.get("images") or []
    return images[0]["url"] if images else None


def describe_text(product):
    price = product.get("price")
    lines = [f"{product['name']} - ${price}", product_url(product)]
    if product.get("status") == "sold-out":
        lines.append("(already sold out)")
    return "\n".join(lines)


def describe_html(product):
    name = html.escape(product["name"])
    price = product.get("price")
    url = product_url(product)
    image = product_image(product)
    sold_out = "<p><em>(already sold out)</em></p>" if product.get("status") == "sold-out" else ""
    image_html = (
        f'<p><a href="{url}"><img src="{image}" alt="{name}" '
        f'style="max-width:400px;width:100%;height:auto;display:block;"></a></p>'
        if image
        else ""
    )
    return (
        '<div style="margin-bottom:24px;">'
        f'<h2 style="margin-bottom:4px;"><a href="{url}">{name}</a></h2>'
        f"<p>${price}</p>"
        f"{image_html}"
        f"{sold_out}"
        "</div>"
    )
