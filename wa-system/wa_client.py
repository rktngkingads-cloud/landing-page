from __future__ import annotations

import os
import re
from typing import Any

import httpx


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def normalize_phone(value: str) -> str:
    normalized = re.sub(r"\D", "", value)
    if not 8 <= len(normalized) <= 15:
        raise ValueError("Phone number must contain 8-15 digits including country code")
    return normalized


def allowed_recipients() -> set[str]:
    raw = os.getenv("WA_ALLOWED_RECIPIENTS", "").strip()
    return {
        normalize_phone(item)
        for item in raw.split(",")
        if item.strip()
    }


async def send_allowed_reply(recipient: str, message: str) -> dict[str, Any]:
    """Send one reply only to a number explicitly present in the allowlist."""
    recipient = normalize_phone(recipient)
    permitted = allowed_recipients()
    if not permitted or recipient not in permitted:
        raise PermissionError("Recipient is not explicitly allowed")

    graph_version = required_env("WA_GRAPH_API_VERSION")
    phone_number_id = required_env("WA_PHONE_NUMBER_ID")
    access_token = required_env("WA_ACCESS_TOKEN")

    url = f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {"preview_url": False, "body": message[:4096]},
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
