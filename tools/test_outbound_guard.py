#!/usr/bin/env python3
"""Local tests for outbound delivery safety guard. No network calls."""

from __future__ import annotations

import argparse
import os

from outbound_guard import CONFIRM_ENV, mask_number, require_outbound_confirmation


def args(target_number: str = "905301234567", confirm_outbound: bool = True) -> argparse.Namespace:
    return argparse.Namespace(target_number=target_number, confirm_outbound=confirm_outbound)


def expect_block(namespace: argparse.Namespace, env_value: str | None) -> None:
    old_value = os.environ.get(CONFIRM_ENV)
    try:
        if env_value is None:
            os.environ.pop(CONFIRM_ENV, None)
        else:
            os.environ[CONFIRM_ENV] = env_value
        try:
            require_outbound_confirmation(namespace)
        except SystemExit:
            return
        raise AssertionError("guard allowed an unsafe outbound configuration")
    finally:
        if old_value is None:
            os.environ.pop(CONFIRM_ENV, None)
        else:
            os.environ[CONFIRM_ENV] = old_value


def expect_allow(namespace: argparse.Namespace, env_value: str) -> None:
    old_value = os.environ.get(CONFIRM_ENV)
    try:
        os.environ[CONFIRM_ENV] = env_value
        assert require_outbound_confirmation(namespace) == namespace.target_number
    finally:
        if old_value is None:
            os.environ.pop(CONFIRM_ENV, None)
        else:
            os.environ[CONFIRM_ENV] = old_value


def main() -> int:
    expect_block(args(confirm_outbound=False), "905301234567")
    expect_block(args(), None)
    expect_block(args(), "905301234568")
    expect_block(args(target_number="05301234567"), "05301234567")
    expect_block(args(target_number="90530123456"), "90530123456")
    expect_allow(args(), "905301234567")
    assert mask_number("905301234567") == "9053****4567"
    print("outbound guard tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
