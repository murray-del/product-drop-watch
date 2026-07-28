#!/usr/bin/env python3
from common import STORE_NAME, fetch_products, send_email, describe_text, describe_html


def main():
    products = fetch_products()
    available = [p for p in products if p.get("status") == "active"]

    if not available:
        send_email(
            f"Daily digest: {STORE_NAME}",
            "Nothing currently available in the shop.",
            "<p>Nothing currently available in the shop.</p>",
        )
        return

    text_body = "\n\n".join(describe_text(p) for p in available)
    html_body = "".join(describe_html(p) for p in available)
    subject = f"Daily digest: {len(available)} piece(s) available at {STORE_NAME}"
    send_email(subject, text_body, html_body)


if __name__ == "__main__":
    main()
