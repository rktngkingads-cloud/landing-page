import hashlib
import hmac

import pytest

from app import extract_text_messages, is_valid_signature, normalize_phone_number


def test_normalize_phone_number():
    assert normalize_phone_number("+60 12-345 6789") == "60123456789"


def test_reject_invalid_phone_number():
    with pytest.raises(ValueError):
        normalize_phone_number("123")


def test_extract_text_messages():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "60123456789",
                                    "type": "text",
                                    "text": {"body": "Hello"},
                                },
                                {
                                    "from": "60123456789",
                                    "type": "image",
                                    "image": {"id": "media-id"},
                                },
                            ]
                        }
                    }
                ]
            }
        ]
    }
    assert extract_text_messages(payload) == [("60123456789", "Hello")]


def test_signature_validation(monkeypatch):
    secret = "test-secret"
    body = b'{"object":"whatsapp_business_account"}'
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    monkeypatch.setenv("WA_APP_SECRET", secret)

    assert is_valid_signature(body, f"sha256={digest}") is True
    assert is_valid_signature(body, "sha256=bad") is False
    assert is_valid_signature(body, None) is False
