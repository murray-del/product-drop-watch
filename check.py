#!/usr/bin/env python3
import json
import os
import smtplib
import urllib.request
from email.mime.text import MIMEText
from pathlib import Path

STORE_NAME = "Paper Frank (FranksLemonadeStand)"
PRODUCTS_URL = "https://frankslemonadestand.bigcartel.com/products.json"
STATE_FILE = Path(__file__).parent / "state" / "seen_ids.json"

GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "murray@murrayabeles.com")


def load_seen_ids():
    if not STATE_FILE.exists():
        return set()
    return set(json.loads(STATE_FILE.read_text())["seen_ids"])


def save_seen_ids(ids):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"seen_ids": sorted(ids)}, indent=2) + "\n")


def fetch_products():
    req = urllib.request.Request(
        PRODUCTS_URL, headers={"User-Agent": "paperfrank-drop-alert/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = NOTIFY_EMAIL
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [NOTIFY_EMAIL], msg.as_string())


def describe(product):
    price = product.get("price")
    url = "https://frankslemonadestand.bigcartel.com" + product["url"]
    lines = [f"{product['name']} - ${price}", url]
    if product.get("status") == "sold-out":
        lines.append("(already sold out)")
    return "\n".join(lines)


def main():
    seen_ids = load_seen_ids()
    first_run = len(seen_ids) == 0

    products = fetch_products()
    current_ids = {p["id"] for p in products}
    new_products = [p for p in products if p["id"] not in seen_ids]

    if first_run:
        send_email(
            f"Monitoring started: {STORE_NAME}",
            f"Now tracking {len(products)} existing product(s) on "
            f"{PRODUCTS_URL}\n\nYou'll get an email as soon as something new drops.",
        )
    elif new_products:
        body = "\n\n".join(describe(p) for p in new_products)
        subject = f"New Paper Frank drop: {new_products[0]['name']}"
        if len(new_products) > 1:
            subject = f"{len(new_products)} new Paper Frank drops!"
        send_email(subject, body)

    save_seen_ids(seen_ids | current_ids)


if __name__ == "__main__":
    main()
