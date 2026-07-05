from __future__ import annotations

import argparse
import asyncio
import sys

from app import send_text_message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send one opt-in WhatsApp message through Meta WhatsApp Cloud API."
    )
    parser.add_argument(
        "--to",
        required=True,
        help="Recipient number with country code, for example 60123456789.",
    )
    parser.add_argument("--message", required=True, help="Text message to send.")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    try:
        result = await send_text_message(args.to, args.message)
    except Exception as exc:  # CLI boundary: return a clear non-zero status.
        print(f"Send failed: {exc}", file=sys.stderr)
        return 1

    message_ids = [item.get("id") for item in result.get("messages", []) if item.get("id")]
    print("Message accepted by WhatsApp Cloud API.")
    if message_ids:
        print("Message ID:", ", ".join(message_ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
