#!/usr/bin/env python3
"""Send one explicitly confirmed live customer scenario to the n8n webhook."""

import argparse
import json
import os
import ssl
import urllib.request
import uuid


DEFAULT_TOKEN = "F9a2Km7Qx8LpN3vB7jR5wY2tH6dK4mS"
WEBHOOK_URL = "https://n8n.filtreoto.online/webhook/evolution-webhook?token={{ $env.WEBHOOK_TOKEN }}"
CUSTOMER_NUMBER = "905308931939"
CUSTOMER_NAME = "Hasandurgun"
SCENARIO_MESSAGE = (
    "Merhaba, 2020 model Renault Clio 1.5 dCi aracim icin yag filtresi "
    "ariyorum. Uyumlu urun ve guncel fiyat konusunda yardimci olur musunuz?"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Required safety switch: this test can send a real WhatsApp reply.",
    )
    args = parser.parse_args()
    if not args.confirm_live:
        parser.error("live delivery blocked; pass --confirm-live explicitly")

    message_id = f"live-scenario-{uuid.uuid4().hex}"
    payload = {
        "data": {
            "key": {
                "remoteJid": f"{CUSTOMER_NUMBER}@s.whatsapp.net",
                "fromMe": False,
                "id": message_id,
            },
            "message": {"conversation": SCENARIO_MESSAGE},
            "pushName": CUSTOMER_NAME,
        }
    }

    request = urllib.request.Request(
        WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    # Use default SSL context (verification enabled)
    context = None
    with urllib.request.urlopen(request, context=context, timeout=20) as response:
        response.read()
        print(
            json.dumps(
                {
                    "httpStatus": response.status,
                    "customer": "********6090",
                    "messageId": message_id,
                    "scenario": "vehicle_filter_price_request",
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())