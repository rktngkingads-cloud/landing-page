from status_parser import extract_delivery_statuses


def test_extract_delivery_status():
    raw_status = {
        "id": "wamid.example",
        "status": "delivered",
        "recipient_id": "60123456789",
        "timestamp": "1710000000",
    }
    payload = {
        "entry": [
            {
                "changes": [
                    {"value": {"statuses": [raw_status]}}
                ]
            }
        ]
    }

    assert extract_delivery_statuses(payload) == [
        {
            "message_id": "wamid.example",
            "status": "delivered",
            "recipient_id": "60123456789",
            "timestamp": 1710000000,
            "error": None,
            "raw": raw_status,
        }
    ]


def test_extract_failed_status_error():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {
                                    "id": "wamid.failed",
                                    "status": "failed",
                                    "recipient_id": "60123456789",
                                    "errors": [{"code": 131000, "title": "Send failed"}],
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    result = extract_delivery_statuses(payload)
    assert result[0]["status"] == "failed"
    assert result[0]["error"] == "Send failed"
