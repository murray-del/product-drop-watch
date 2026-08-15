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
PRODUCTS_URL = STORE_BASE_URL + "/products.json"

GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "murray@murrayabeles.com")


def fetch_products():
    req = urllib.request.Request(
        PRODUCTS_URL, headers={"User-Agent": "product-watch/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


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
