from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from cooldown import ReplyCooldown
from status_parser import extract_delivery_statuses
from storage import init_database, list_messages, message_exists, save_message, status_summary
from wa_client import allowed_recipients, normalize_phone, required_env, send_allowed_reply

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("wa-system")


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number") from exc


cooldown = ReplyCooldown(
    minimum_seconds=env_float("WA_COOLDOWN_MIN_SECONDS", 16.0),
    maximum_seconds=env_float("WA_COOLDOWN_MAX_SECONDS", 20.0),
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield
    await cooldown.shutdown()


app = FastAPI(
    title="WA Auto Reply Service",
    version="1.0.0",
    lifespan=lifespan,
)


def is_valid_signature(raw_body: bytes, signature_header: str | None) -> bool:
    app_secret = os.getenv("WA_APP_SECRET", "").strip()
    if not app_secret:
        logger.warning("WA_APP_SECRET is empty; webhook signature validation is disabled")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    supplied = signature_header.removeprefix("sha256=")
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)


def parse_timestamp(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def extract_incoming_texts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []) or []:
                if message.get("type") != "text":
                    continue

                message_id = message.get("id")
                sender = message.get("from")
                body = (message.get("text") or {}).get("body")
                if not message_id or not sender or not body:
                    continue

                result.append(
                    {
                        "message_id": str(message_id),
                        "sender": normalize_phone(str(sender)),
                        "body": str(body).strip(),
                        "timestamp": parse_timestamp(message.get("timestamp")),
                        "raw": message,
                    }
                )
    return result


def reply_text(incoming_text: str) -> str:
    rules_raw = os.getenv("WA_AUTO_REPLY_RULES", "").strip()
    if rules_raw:
        try:
            rules = json.loads(rules_raw)
        except json.JSONDecodeError:
            logger.exception("WA_AUTO_REPLY_RULES is invalid JSON")
        else:
            if isinstance(rules, dict):
                normalized = incoming_text.casefold()
                for keyword, response in rules.items():
                    if str(keyword).casefold() in normalized and str(response).strip():
                        return str(response).strip()

    return os.getenv(
        "WA_AUTO_REPLY_TEXT",
        "Balasan otomatis: Terima kasih, pesan Anda sudah diterima.",
    ).strip()


async def send_and_record(recipient: str, message: str) -> None:
    try:
        result = await send_allowed_reply(recipient, message)
    except (httpx.HTTPError, RuntimeError, ValueError, PermissionError):
        logger.exception("Automatic reply failed for recipient ending %s", recipient[-4:])
        return

    for item in result.get("messages", []) or []:
        message_id = item.get("id")
        if not message_id:
            continue
        save_message(
            message_id=str(message_id),
            direction="outgoing",
            phone=recipient,
            body=message,
            status="accepted",
            raw=result,
        )


def require_admin(value: str | None) -> None:
    expected = os.getenv("WA_ADMIN_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="WA_ADMIN_API_KEY is not configured")
    if not value or not hmac.compare_digest(value, expected):
        raise HTTPException(status_code=401, detail="Invalid admin API key")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "cooldown_seconds": {
            "minimum": cooldown.minimum_seconds,
            "maximum": cooldown.maximum_seconds,
        },
        "allowed_recipient_count": len(allowed_recipients()),
        "message_summary": status_summary(),
    }


@app.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> str:
    expected = required_env("WA_VERIFY_TOKEN")
    if mode == "subscribe" and token and hmac.compare_digest(token, expected):
        return challenge or ""
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@app.post("/webhook")
async def webhook(request: Request) -> dict[str, int | str]:
    raw_body = await request.body()
    if not is_valid_signature(raw_body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = json.loads(raw_body)
    incoming_count = 0
    scheduled_count = 0
    status_count = 0

    for status in extract_delivery_statuses(payload):
        save_message(
            message_id=status["message_id"],
            direction="outgoing",
            phone=status["recipient_id"],
            body="",
            status=status["status"],
            event_timestamp=status["timestamp"],
            error=status["error"],
            raw=status["raw"],
        )
        status_count += 1

    permitted = allowed_recipients()
    for incoming in extract_incoming_texts(payload):
        incoming_count += 1
        if message_exists(incoming["message_id"]):
            logger.info("Duplicate webhook ignored: %s", incoming["message_id"])
            continue

        save_message(
            message_id=incoming["message_id"],
            direction="incoming",
            phone=incoming["sender"],
            body=incoming["body"],
            status="received",
            event_timestamp=incoming["timestamp"],
            raw=incoming["raw"],
        )

        if incoming["sender"] not in permitted:
            logger.info("Incoming number is not in WA_ALLOWED_RECIPIENTS")
            continue

        response = reply_text(incoming["body"])
        if not response:
            continue

        cooldown.schedule(incoming["sender"], response, send_and_record)
        scheduled_count += 1

    return {
        "status": "accepted",
        "incoming_messages": incoming_count,
        "scheduled_replies": scheduled_count,
        "delivery_updates": status_count,
    }


@app.get("/messages")
async def messages(
    limit: int = Query(default=100, ge=1, le=500),
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> dict[str, Any]:
    require_admin(x_admin_key)
    return {
        "items": list_messages(limit),
        "summary": status_summary(),
        "note": "Delivery status is available; arbitrary user online/active presence is not.",
    }
