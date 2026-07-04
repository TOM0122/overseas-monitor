from __future__ import annotations

from datetime import datetime, timezone

import pytest

import utils.db as db


class FakeResp:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, table):
        self.table = table
        self.filters: dict = {}

    def select(self, *_a, **_k):
        return self

    def gte(self, *a, **k):
        return self

    def lt(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def upsert(self, rows, on_conflict=None):
        self.table.upserted = (rows, on_conflict)
        return self

    def execute(self):
        return FakeResp([{"table": self.table.name, "filters": self.filters}])


class FakeTable:
    def __init__(self, name):
        self.name = name
        self.upserted = None

    # query builder entrypoints delegate to a FakeQuery
    def select(self, *a, **k):
        return FakeQuery(self)

    def upsert(self, rows, on_conflict=None):
        return FakeQuery(self).upsert(rows, on_conflict)


class FakeClient:
    def __init__(self):
        self.tables: dict[str, FakeTable] = {}

    def table(self, name):
        return self.tables.setdefault(name, FakeTable(name))


def make_repo(monkeypatch, table_env=None):
    if table_env is None:
        monkeypatch.delenv("OFFSITE_DEALS_TABLE", raising=False)
    else:
        monkeypatch.setenv("OFFSITE_DEALS_TABLE", table_env)
    monkeypatch.setenv("SUPABASE_URL", "http://x")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    monkeypatch.setattr(db, "create_client", lambda url, key: FakeClient())
    monkeypatch.setattr(db, "load_dotenv", lambda *a, **k: None)
    return db.SupabaseRepository()


def test_default_table_is_legacy(monkeypatch):
    repo = make_repo(monkeypatch)
    assert repo.offsite_table == "slickdeals_deals"


def test_env_switches_to_offsite_table(monkeypatch):
    repo = make_repo(monkeypatch, table_env="offsite_deals")
    assert repo.offsite_table == "offsite_deals"
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 2, tzinfo=timezone.utc)
    rows = repo.fetch_offsite_deals_between(start, end, category="fan")
    assert rows[0]["table"] == "offsite_deals"
    assert rows[0]["filters"]["category"] == "fan"


def test_legacy_methods_delegate_to_offsite(monkeypatch):
    repo = make_repo(monkeypatch, table_env="offsite_deals")
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 2, tzinfo=timezone.utc)
    # legacy fetch delegates to the configured table
    rows = repo.fetch_slickdeals_deals_between(start, end)
    assert rows[0]["table"] == "offsite_deals"
    # legacy upsert delegates to the configured table
    repo.upsert_slickdeals_deals([{"deal_id": "d1", "title": "Portable Fan"}])
    assert repo.client.tables["offsite_deals"].upserted[1] == "deal_id"
