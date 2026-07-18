#!/usr/bin/env python3
"""Safety guard for scripts that can trigger live outbound WhatsApp delivery."""

from __future__ import annotations

import argparse
import os
import re


CONFIRM_ENV = "CONFIRMED_TARGET_NUMBER"
_TR_NUMBER_RE = re.compile(r"^90\d{10}$")


def add_outbound_confirmation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--target-number",
        required=True,
        help="Explicitly approved recipient number, e.g. 905301234567.",
    )
    parser.add_argument(
        "--confirm-outbound",
        action="store_true",
        help="Required safety switch for commands that can trigger WhatsApp delivery.",
    )


def mask_number(number: str) -> str:
    if len(number) <= 4:
        return "*" * len(number)
    return f"{number[:4]}{'*' * (len(number) - 8)}{number[-4:]}"


def require_outbound_confirmation(args: argparse.Namespace) -> str:
    target_number = getattr(args, "target_number", "") or ""
    confirmed_number = os.environ.get(CONFIRM_ENV, "")

    if not getattr(args, "confirm_outbound", False):
        raise SystemExit(
            "outbound blocked: pass --confirm-outbound only after written number approval"
        )
    if not target_number:
        raise SystemExit("outbound blocked: --target-number is required")
    if not _TR_NUMBER_RE.fullmatch(target_number):
        raise SystemExit(
            "outbound blocked: --target-number must be 12 digits and start with 90"
        )
    if not confirmed_number:
        raise SystemExit(f"outbound blocked: set {CONFIRM_ENV} to the approved number")
    if confirmed_number != target_number:
        raise SystemExit(
            f"outbound blocked: {CONFIRM_ENV} does not match --target-number"
        )

    return target_number
