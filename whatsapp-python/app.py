from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("whatsapp-bot")

app = FastAPI(title="WhatsApp Cloud API Auto Reply", version="1.0.0")


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def normalize_phone_number(value: str) -> str:
    """Return an international phone number as digits only."""
    normalized = re.sub(r"\D", "", value)
    if not 8 <= len(normalized) <= 15:
        raise ValueError("Phone number must contain 8-15 digits including country code")
    return normalized


def allowed_recipients() -> set[str]:
    raw = os.getenv("WA_ALLOWED_RECIPIENTS", "").strip()
    if not raw:
        return set()

    recipients: set[str] = set()
    for item in raw.split(","):
        item = item.strip()
        if item:
            recipients.add(normalize_phone_number(item))
    return recipients


def is_valid_signature(raw_body: bytes, signature_header: str | None) -> bool:
    app_secret = os.getenv("WA_APP_SECRET", "").strip()
    if not app_secret:
        logger.warning("WA_APP_SECRET is not configured; webhook signature validation is disabled")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    supplied = signature_header.removeprefix("sha256=")
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)


def extract_text_messages(payload: dict[str, Any]) -> list[tuple[str, str]]:
    messages: list[tuple[str, str]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []) or []:
                if message.get("type") != "text":
                    continue
                sender = message.get("from")
                body = (message.get("text") or {}).get("body")
                if sender and body:
                    messages.append((normalize_phone_number(sender), str(body).strip()))
    return messages


async def send_text_message(recipient: str, message: str) -> dict[str, Any]:
    recipient = normalize_phone_number(recipient)
    recipients = allowed_recipients()
    if recipients and recipient not in recipients:
        raise PermissionError("Recipient is not in WA_ALLOWED_RECIPIENTS")

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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> str:
    expected_token = required_env("WA_VERIFY_TOKEN")
    if mode == "subscribe" and token and hmac.compare_digest(token, expected_token):
        return challenge or ""
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@app.post("/webhook")
async def receive_webhook(request: Request) -> dict[str, str]:
    raw_body = await request.body()
    if not is_valid_signature(raw_body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    auto_reply = os.getenv(
        "WA_AUTO_REPLY_TEXT",
        "Terima kasih. Pesan Anda sudah diterima dan akan segera diproses.",
    ).strip()

    for sender, incoming_text in extract_text_messages(payload):
        logger.info("Incoming WhatsApp text from %s (%d characters)", sender, len(incoming_text))
        if not auto_reply:
            continue
        try:
            await send_text_message(sender, auto_reply)
        except PermissionError:
            logger.warning("Skipped sender %s because it is not in the recipient allowlist", sender)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            # Return 200 so Meta does not repeatedly redeliver a webhook that has already been processed.
            logger.exception("Failed to send auto reply: %s", exc)

    return {"status": "accepted"}
