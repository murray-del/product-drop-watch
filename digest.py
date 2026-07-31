#!/usr/bin/env python3
import html

from common import STORE_NAME, fetch_products, send_email, describe_text, describe_html, listed_at


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
    products = fetch_products()
    available = [p for p in products if p.get("status") == "active"]
    history = sorted(products, key=lambda p: p["created_at"], reverse=True)

    if available:
        text_body = "\n\n".join(describe_text(p) for p in available)
        html_body = "".join(describe_html(p) for p in available)
        subject = f"Daily digest: {len(available)} piece(s) available at {STORE_NAME}"
    else:
        text_body = "Nothing currently available in the shop."
        html_body = "<p>Nothing currently available in the shop.</p>"
        subject = f"Daily digest: {STORE_NAME}"

    text_body += "\n\n---\n\n" + build_table_text(history)
    html_body += "<hr>" + build_table_html(history)

    send_email(subject, text_body, html_body)


if __name__ == "__main__":
    main()
