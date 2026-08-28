#!/usr/bin/env python3
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from common import (
    STORE_NAME,
    fetch_products,
    send_email,
    describe_text,
    describe_html,
    listed_at,
    format_duration,
)

_state_subdir = os.environ.get("STATE_SUBDIR")
STATE_DIR = (
    Path(__file__).parent / "state" / _state_subdir
    if _state_subdir
    else Path(__file__).parent / "state"
)
SOLD_TIMES_FILE = STATE_DIR / "sold_times.json"
LAST_DIGEST_FILE = STATE_DIR / "last_digest_at.json"


def load_sold_times():
    if not SOLD_TIMES_FILE.exists():
        return []
    return json.loads(SOLD_TIMES_FILE.read_text())


def load_last_digest_at():
    if not LAST_DIGEST_FILE.exists():
        return None
    return json.loads(LAST_DIGEST_FILE.read_text())["last_digest_at"]


def save_last_digest_at(iso_timestamp):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LAST_DIGEST_FILE.write_text(json.dumps({"last_digest_at": iso_timestamp}, indent=2) + "\n")


def build_sold_section_text(sold_entries):
    if not sold_entries:
        return "Sold since last digest: nothing."
    lines = ["Sold since last digest:", ""]
    for e in sold_entries:
        lines.append(f"{e['name']} - sold after {format_duration(e['minutes_to_sell'])}")
    return "\n".join(lines)


def build_sold_section_html(sold_entries):
    if not sold_entries:
        return "<h3>Sold since last digest</h3><p>Nothing sold since the last digest.</p>"
    items = "".join(
        f"<li>{html.escape(e['name'])} — sold after {format_duration(e['minutes_to_sell'])}</li>"
        for e in sold_entries
    )
    return f"<h3>Sold since last digest</h3><ul>{items}</ul>"


def build_table_text(products):
    lines = ["Full listing history (newest first):", ""]
    for p in products:
        date_str, time_str = listed_at(p)
        lines.append(f"{p['name']} - ${p.get('price')} - {date_str} {time_str}")
    return "\n".join(lines)


def build_table_html(products):
    rows = []
    for p in products:
        date_str, time_str = listed_at(p)
        rows.append(
            "<tr>"
            f"<td style=\"padding:4px 12px 4px 0;\">{html.escape(p['name'])}</td>"
            f"<td style=\"padding:4px 12px;\">${p.get('price')}</td>"
            f"<td style=\"padding:4px 12px;\">{date_str}</td>"
            f"<td style=\"padding:4px 0;\">{time_str}</td>"
            "</tr>"
        )
    return (
        "<h3>Full listing history (newest first)</h3>"
        "<table style=\"border-collapse:collapse;\">"
        "<tr>"
        '<th style="text-align:left;padding:4px 12px 4px 0;">Name</th>'
        '<th style="text-align:left;padding:4px 12px;">Price</th>'
        '<th style="text-align:left;padding:4px 12px;">Date</th>'
        '<th style="text-align:left;padding:4px 0;">Time</th>'
        "</tr>" + "".join(rows) + "</table>"
    )


def main():
    now = datetime.now(timezone.utc).isoformat()
    prev_digest_at = load_last_digest_at()

    products = fetch_products()
    available = [p for p in products if p.get("status") == "active"]
    history = sorted(products, key=lambda p: p["created_at"], reverse=True)

    recently_sold = []
    if prev_digest_at:
        recently_sold = [
            e for e in load_sold_times() if e["sold_out_detected_at"] > prev_digest_at
        ]
        recently_sold.sort(key=lambda e: e["sold_out_detected_at"], reverse=True)

    if available:
        text_body = "\n\n".join(describe_text(p) for p in available)
        html_body = "".join(describe_html(p) for p in available)
        subject = f"Daily digest: {len(available)} piece(s) available at {STORE_NAME}"
    else:
        text_body = "Nothing currently available in the shop."
        html_body = "<p>Nothing currently available in the shop.</p>"
        subject = f"Daily digest: {STORE_NAME}"

    text_body += "\n\n---\n\n" + build_sold_section_text(recently_sold)
    html_body += "<hr>" + build_sold_section_html(recently_sold)

    text_body += "\n\n---\n\n" + build_table_text(history)
    html_body += "<hr>" + build_table_html(history)

    send_email(subject, text_body, html_body)
    save_last_digest_at(now)


if __name__ == "__main__":
    main()
