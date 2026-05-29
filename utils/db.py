from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

logger = logging.getLogger(__name__)


class SupabaseRepository:
    """Small data-access wrapper around Supabase tables used by this project."""

    def __init__(self, url: str | None = None, key: str | None = None) -> None:
        load_dotenv()
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

        if not self.url:
            raise ValueError("SUPABASE_URL is required")
        if not self.key:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY is required")

        self.client: Client = create_client(self.url, self.key)

    def upsert_slickdeals_deals(self, deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Insert or update Slickdeals rows by unique deal_id."""
        if not deals:
            logger.info("No Slickdeals deals to upsert")
            return []

        response = (
            self.client.table("slickdeals_deals")
            .upsert(deals, on_conflict="deal_id")
            .execute()
        )
        logger.info("Upserted %s Slickdeals deals", len(response.data or []))
        return response.data or []

    def insert_amazon_snapshots(self, snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Insert Amazon snapshot rows. Snapshots are append-only by design."""
        if not snapshots:
            logger.info("No Amazon snapshots to insert")
            return []

        response = self.client.table("amazon_snapshots").insert(snapshots).execute()
        logger.info("Inserted %s Amazon snapshots", len(response.data or []))
        return response.data or []

    def upsert_amazon_bestsellers(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Insert or update Amazon best-seller ranks by category, ASIN, and date."""
        if not rows:
            logger.info("No Amazon best-seller rows to upsert")
            return []

        response = (
            self.client.table("amazon_bestsellers")
            .upsert(rows, on_conflict="category_id,asin,snapshot_date")
            .execute()
        )
        logger.info("Upserted %s Amazon best-seller rows", len(response.data or []))
        return response.data or []

    def fetch_slickdeals_deals_between(
        self,
        start_utc: datetime,
        end_utc: datetime,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            self.client.table("slickdeals_deals")
            .select("*")
            .gte("scraped_at", start_utc.isoformat())
            .lt("scraped_at", end_utc.isoformat())
            .order("thumbs_up", desc=True)
        )
        if category:
            query = query.eq("category", category)

        response = query.execute()
        return response.data or []

    def fetch_amazon_snapshots_between(
        self,
        start_utc: datetime,
        end_utc: datetime,
        asins: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            self.client.table("amazon_snapshots")
            .select("*")
            .gte("snapshot_at", start_utc.isoformat())
            .lt("snapshot_at", end_utc.isoformat())
            .order("snapshot_at", desc=True)
        )
        if asins:
            query = query.in_("asin", asins)

        response = query.execute()
        return response.data or []

    def fetch_amazon_bestsellers_between(
        self,
        start_utc: datetime,
        end_utc: datetime,
        category_id: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            self.client.table("amazon_bestsellers")
            .select("*")
            .gte("snapshot_at", start_utc.isoformat())
            .lt("snapshot_at", end_utc.isoformat())
            .order("rank", desc=False)
        )
        if category_id:
            query = query.eq("category_id", category_id)

        response = query.execute()
        return response.data or []

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generic insert helper for small operational scripts."""
        if not rows:
            return []
        response = self.client.table(table).insert(rows).execute()
        return response.data or []

    def upsert_rows(
        self,
        table: str,
        rows: list[dict[str, Any]],
        on_conflict: str,
    ) -> list[dict[str, Any]]:
        """Generic upsert helper for tables with a known unique key."""
        if not rows:
            return []
        response = self.client.table(table).upsert(rows, on_conflict=on_conflict).execute()
        return response.data or []


def get_repository() -> SupabaseRepository:
    return SupabaseRepository()
