#!/usr/bin/env python3
"""Send explicitly confirmed test payloads to the live n8n webhook.

This script can trigger real WhatsApp replies. It is blocked unless the target
number is approved in both CLI args and CONFIRMED_TARGET_NUMBER.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
import uuid

from outbound_guard import (
    add_outbound_confirmation_args,
    mask_number,
    require_outbound_confirmation,
)


WEBHOOK_BASE_URL = "https://n8n.filtreoto.online/webhook/evolution-webhook"
DEFAULT_SENDER_NAME = "ApprovedTestCustomer"

SCENARIOS = {
    "normal": [
        ("Normal Musteri Mesaji", "Merhaba, Renault Clio 2018 icin yag filtresi ariyorum", False),
    ],
    "manual-on": [
        ("Yonetici ++ Komutu", "++", True),
    ],
    "manual-off": [
        ("Yonetici -- Komutu", "--", True),
    ],
    "customer-plus": [
        ("Musteri ++ Yazar", "++", False),
    ],
    "batch": [
        ("Batch 1", "Merhaba", False),
        ("Batch 2", "Fiat Egea 2021", False),
        ("Batch 3", "Yag filtresi ariyorum", False),
    ],
    "duplicate": [
        ("Duplicate Ilk", "Test mesaji", False),
        ("Duplicate Tekrar", "Ayni mesaj tekrar", False),
    ],
    "unclear": [
        ("Belirsiz Mesaj", "?", False),
    ],
    "price": [
        ("Fiyat Sorusu", "Fiat Egea 2021 icin yag filtresi fiyati ne kadar?", False),
    ],
    "vin": [
        ("Sase Numarasi", "BMW 320d 2019 aracim var. Sase numaram WBAPL5105KA123456", False),
    ],
    "handoff": [
        ("Sikayet", "Siparisim hasarli geldi, iade etmek istiyorum", False),
    ],
}


def webhook_url() -> str:
    token = os.environ.get("WEBHOOK_TOKEN")
    if not token:
        raise SystemExit("outbound blocked: WEBHOOK_TOKEN environment variable is required")
    return f"{WEBHOOK_BASE_URL}?token={token}"


def build_payload(message_text: str, sender_number: str, sender_name: str, from_me: bool, message_id: str) -> dict:
    return {
        "data": {
            "key": {
                "remoteJid": f"{sender_number}@s.whatsapp.net",
                "fromMe": from_me,
                "id": message_id,
            },
            "message": {"conversation": message_text},
            "pushName": sender_name,
        }
    }


def send_webhook(
    message_text: str,
    sender_number: str,
    sender_name: str,
    from_me: bool = False,
    message_id: str | None = None,
) -> bool:
    message_id = message_id or str(uuid.uuid4())
    payload = build_payload(message_text, sender_number, sender_name, from_me, message_id)
    request = urllib.request.Request(
        webhook_url(),
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, context=None, timeout=10) as response:
            result = response.read().decode("utf-8")
            print(f"  [OK] {response.status} - {result[:100]}")
            return True
    except urllib.error.HTTPError as exc:
        print(f"  [HATA] {exc.code} - {exc.read().decode('utf-8')[:100]}")
        return False
    except Exception as exc:
        print(f"  [HATA] {exc}")
        return False


def selected_steps(args: argparse.Namespace) -> list[tuple[str, str, bool, str]]:
    if args.message:
        return [("Custom Mesaj", args.message, args.from_me, str(uuid.uuid4()))]

    scenario_names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    duplicate_id = str(uuid.uuid4())
    steps: list[tuple[str, str, bool, str]] = []
    for scenario_name in scenario_names:
        for label, text, from_me in SCENARIOS[scenario_name]:
            message_id = duplicate_id if scenario_name == "duplicate" else str(uuid.uuid4())
            steps.append((label, text, from_me, message_id))
    return steps


def main() -> int:
    parser = argparse.ArgumentParser()
    add_outbound_confirmation_args(parser)
    parser.add_argument("--sender-name", default=DEFAULT_SENDER_NAME)
    parser.add_argument("--message", help="Send one custom webhook message instead of a named scenario.")
    parser.add_argument("--from-me", action="store_true", help="Mark custom message as fromMe=true.")
    parser.add_argument(
        "--scenario",
        choices=["all", *SCENARIOS.keys()],
        default="normal",
        help="Named scenario to send. Defaults to one normal customer message.",
    )
    args = parser.parse_args()

    target_number = require_outbound_confirmation(args)
    steps = selected_steps(args)

    print(f"Target: {mask_number(target_number)}")
    print(f"Messages to send: {len(steps)}")
    for index, (label, text, from_me, message_id) in enumerate(steps, 1):
        print(f"\n[{index}/{len(steps)}] {label}")
        print(f"  fromMe: {from_me}")
        send_webhook(text, target_number, args.sender_name, from_me, message_id)
        if index < len(steps):
            time.sleep(2 if args.scenario == "batch" else 1)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
