from __future__ import annotations

from typing import Any


def parse_timestamp(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def extract_delivery_statuses(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract official delivery states from a WhatsApp webhook payload."""
    statuses: list[dict[str, Any]] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for item in value.get("statuses", []) or []:
                message_id = item.get("id")
                state = item.get("status")
                if not message_id or not state:
                    continue

                errors = item.get("errors") or []
                error: str | None = None
                if errors:
                    first = errors[0]
                    error = str(
                        first.get("message")
                        or first.get("title")
                        or first.get("code")
                        or "Unknown delivery error"
                    )

                statuses.append(
                    {
                        "message_id": str(message_id),
                        "status": str(state),
                        "recipient_id": str(item.get("recipient_id") or "unknown"),
                        "timestamp": parse_timestamp(item.get("timestamp")),
                        "error": error,
                        "raw": item,
                    }
                )

    return statuses
