import os
from pathlib import Path

from contact_store import (
    get_contact,
    increment_reply_counter,
    init_contact_store,
    is_opted_in,
    list_contacts,
    replies_today,
    set_opt_in,
    set_opt_out,
)


def test_contact_opt_in_and_opt_out(tmp_path: Path, monkeypatch):
    database = tmp_path / "contacts.db"
    monkeypatch.setenv("WA_DB_PATH", str(database))
    init_contact_store()

    set_opt_in(
        "60123456789",
        source="manual-consent-record",
        note="Consent recorded by administrator",
        consent_at=1710000000,
    )

    assert is_opted_in("60123456789") is True
    contact = get_contact("60123456789")
    assert contact is not None
    assert contact["consent_source"] == "manual-consent-record"
    assert len(list_contacts()) == 1

    set_opt_out("60123456789")
    assert is_opted_in("60123456789") is False


def test_daily_reply_counter(tmp_path: Path, monkeypatch):
    database = tmp_path / "counters.db"
    monkeypatch.setenv("WA_DB_PATH", str(database))
    init_contact_store()

    assert replies_today("60123456789", "2026-07-05") == 0
    increment_reply_counter("60123456789", "2026-07-05")
    increment_reply_counter("60123456789", "2026-07-05")
    assert replies_today("60123456789", "2026-07-05") == 2
