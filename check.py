#!/usr/bin/env python3
import json
import os
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

_state_subdir = os.environ.get("STATE_SUBDIR")
STATE_DIR = (
    Path(__file__).parent / "state" / _state_subdir
    if _state_subdir
    else Path(__file__).parent / "state"
)
STATE_FILE = STATE_DIR / "seen_ids.json"
STATUS_FILE = STATE_DIR / "status.json"
SOLD_TIMES_FILE = STATE_DIR / "sold_times.json"
POSITIONS_FILE = STATE_DIR / "positions.json"
REORDER_EVENTS_FILE = STATE_DIR / "reorder_events.json"


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


def load_positions():
    if not POSITIONS_FILE.exists():
        return {}
    return json.loads(POSITIONS_FILE.read_text())


def save_positions(positions):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    POSITIONS_FILE.write_text(json.dumps(positions, indent=2, sort_keys=True) + "\n")


def load_reorder_events():
    if not REORDER_EVENTS_FILE.exists():
        return []
    return json.loads(REORDER_EVENTS_FILE.read_text())


def save_reorder_events(events):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    REORDER_EVENTS_FILE.write_text(json.dumps(events, indent=2) + "\n")


def detect_reorder(products, prev_positions):
    """Detect if the relative order of items present in both snapshots changed
    (ignores pure position-number shifts caused by new items being inserted)."""
    if not prev_positions:
        return None

    names = {str(p["id"]): p["name"] for p in products}
    current_positions = {str(p["id"]): p["position"] for p in products}
    common_ids = set(prev_positions) & set(current_positions)
    if len(common_ids) < 2:
        return None

    prev_order = sorted(common_ids, key=lambda i: prev_positions[i])
    current_order = sorted(common_ids, key=lambda i: current_positions[i])
    if prev_order == current_order:
        return None

    return {
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "previous_order": [names[i] for i in prev_order],
        "new_order": [names[i] for i in current_order],
    }


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
    prev_positions = load_positions()

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
        subject = f"New drop at {STORE_NAME}: {new_products[0]['name']}"
        if len(new_products) > 1:
            subject = f"{len(new_products)} new drops at {STORE_NAME}!"
        send_email(subject, text_body, html_body)

    sold_events = detect_sold_out(products, prev_status)
    log = load_sold_times()
    log.extend(sold_events)
    save_sold_times(log)

    reorder_event = detect_reorder(products, prev_positions)
    events = load_reorder_events()
    if reorder_event:
        events.append(reorder_event)
        numbered = "\n".join(f"{i+1}. {name}" for i, name in enumerate(reorder_event["new_order"]))
        send_email(
            f"Shop item order changed: {STORE_NAME}",
            "The relative order of items in the shop just changed - possibly a sign "
            f"of rearranging ahead of a new listing.\n\nNew order:\n{numbered}",
        )
    save_reorder_events(events)

    save_status({str(p["id"]): p.get("status") for p in products})
    save_positions({str(p["id"]): p["position"] for p in products})
    save_seen_ids(seen_ids | current_ids)


if __name__ == "__main__":
    main()
