#!/usr/bin/env python3
"""Send one explicitly confirmed live customer scenario to the n8n webhook."""

import argparse
import json
import os
import urllib.request
import uuid

from outbound_guard import (
    add_outbound_confirmation_args,
    mask_number,
    require_outbound_confirmation,
)

WEBHOOK_BASE_URL = "https://n8n.filtreoto.online/webhook/evolution-webhook"
CUSTOMER_NAME = "ApprovedLiveCustomer"
SCENARIO_MESSAGE = (
    "Merhaba, 2020 model Renault Clio 1.5 dCi aracim icin yag filtresi "
    "ariyorum. Uyumlu urun ve guncel fiyat konusunda yardimci olur musunuz?"
)


def webhook_url() -> str:
    token = os.environ.get("WEBHOOK_TOKEN")
    if not token:
        raise SystemExit("outbound blocked: WEBHOOK_TOKEN environment variable is required")
    return f"{WEBHOOK_BASE_URL}?token={token}"


def main() -> int:
    parser = argparse.ArgumentParser()
    add_outbound_confirmation_args(parser)
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Legacy safety switch kept for compatibility; --confirm-outbound is also required.",
    )
    args = parser.parse_args()
    if not args.confirm_live:
        parser.error("live delivery blocked; pass --confirm-live explicitly")
    target_number = require_outbound_confirmation(args)

    message_id = f"live-scenario-{uuid.uuid4().hex}"
    payload = {
        "data": {
            "key": {
                "remoteJid": f"{target_number}@s.whatsapp.net",
                "fromMe": False,
                "id": message_id,
            },
            "message": {"conversation": SCENARIO_MESSAGE},
            "pushName": CUSTOMER_NAME,
        }
    }

    request = urllib.request.Request(
        webhook_url(),
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, context=None, timeout=20) as response:
        response.read()
        print(
            json.dumps(
                {
                    "httpStatus": response.status,
                    "customer": mask_number(target_number),
                    "messageId": message_id,
                    "scenario": "vehicle_filter_price_request",
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
