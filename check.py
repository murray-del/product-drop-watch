#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

from common import (
    STORE_NAME,
    PRODUCTS_URL,
    fetch_products,
    send_email,
    describe_text,
    describe_html,
)

STATE_DIR = Path(__file__).parent / "state"
STATE_FILE = STATE_DIR / "seen_ids.json"
STATUS_FILE = STATE_DIR / "status.json"
SOLD_TIMES_FILE = STATE_DIR / "sold_times.json"


def load_seen_ids():
    if not STATE_FILE.exists():
        return set()
    return set(json.loads(STATE_FILE.read_text())["seen_ids"])


def save_seen_ids(ids):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"seen_ids": sorted(ids)}, indent=2) + "\n")


def load_status():
    if not STATUS_FILE.exists():
        return {}
    return json.loads(STATUS_FILE.read_text())


def save_status(status):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")


def load_sold_times():
    if not SOLD_TIMES_FILE.exists():
        return []
    return json.loads(SOLD_TIMES_FILE.read_text())


def save_sold_times(entries):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SOLD_TIMES_FILE.write_text(json.dumps(entries, indent=2) + "\n")


def detect_sold_out(products, prev_status):
    now = datetime.now(timezone.utc)
    events = []
    for p in products:
        pid = str(p["id"])
        if prev_status.get(pid) == "active" and p.get("status") == "sold-out":
            created = datetime.fromisoformat(p["created_at"].replace("Z", "+00:00"))
            events.append(
                {
                    "id": p["id"],
                    "name": p["name"],
                    "created_at": p["created_at"],
                    "sold_out_detected_at": now.isoformat(),
                    "minutes_to_sell": round((now - created).total_seconds() / 60, 1),
                }
            )
    return events


def main():
    seen_ids = load_seen_ids()
    first_run = len(seen_ids) == 0
    prev_status = load_status()

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
        subject = f"New drop: {new_products[0]['name']}"
        if len(new_products) > 1:
            subject = f"{len(new_products)} new drops!"
        send_email(subject, text_body, html_body)

    sold_events = detect_sold_out(products, prev_status)
    if sold_events:
        log = load_sold_times()
        log.extend(sold_events)
        save_sold_times(log)

    save_status({str(p["id"]): p.get("status") for p in products})
    save_seen_ids(seen_ids | current_ids)


if __name__ == "__main__":
    main()
