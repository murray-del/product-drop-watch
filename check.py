#!/usr/bin/env python3
import json
from pathlib import Path

from common import (
    STORE_NAME,
    PRODUCTS_URL,
    fetch_products,
    send_email,
    describe_text,
    describe_html,
)

STATE_FILE = Path(__file__).parent / "state" / "seen_ids.json"


def load_seen_ids():
    if not STATE_FILE.exists():
        return set()
    return set(json.loads(STATE_FILE.read_text())["seen_ids"])


def save_seen_ids(ids):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"seen_ids": sorted(ids)}, indent=2) + "\n")


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
        text_body = "\n\n".join(describe_text(p) for p in new_products)
        html_body = "".join(describe_html(p) for p in new_products)
        subject = f"New Paper Frank drop: {new_products[0]['name']}"
        if len(new_products) > 1:
            subject = f"{len(new_products)} new Paper Frank drops!"
        send_email(subject, text_body, html_body)

    save_seen_ids(seen_ids | current_ids)


if __name__ == "__main__":
    main()
