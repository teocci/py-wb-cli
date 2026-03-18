"""Typed client for WB Promotion API operations."""

from __future__ import annotations

from typing import Any

from wb.client.http import WbHttpClient
from wb.core.constants import (
    EP_ACCOUNT_BALANCE,
    EP_BID_SET,
    EP_BUDGET_DEPOSIT,
    EP_CAMPAIGN_BUDGET,
    EP_CAMPAIGN_CREATE,
    EP_CAMPAIGN_FULLSTATS,
    EP_CAMPAIGN_ITEMS,
    EP_CAMPAIGN_LIST,
    EP_CAMPAIGN_PAUSE,
    EP_CAMPAIGN_PLACEMENTS,
    EP_CAMPAIGN_RENAME,
    EP_CAMPAIGN_START,
    EP_CAMPAIGN_STOP,
    EP_CLUSTER_ACTIVE,
    EP_CLUSTER_ALL,
    EP_CLUSTER_STATS,
    EP_ELIGIBLE_ITEMS,
    EP_ELIGIBLE_SUBJECTS,
    EP_RECOMMENDED_BID,
)

__all__ = ['PromotionClient']

# Deposit type 1 = add funds to campaign budget
_DEPOSIT_TYPE_ADD = 1


class PromotionClient:
    """Typed wrapper around WbHttpClient for Promotion API reads.

    Returns raw API dicts; model conversion is the service layer's job.

    Attributes:
        http: Underlying HTTP client.
    """

    def __init__(self, http: WbHttpClient) -> None:
        self._http = http

    def list_campaigns(
            self,
            status: list[int] | None = None,
            type_: list[int] | None = None,
    ) -> list[dict]:
        """List all campaigns, optionally filtered by status or type.

        Args:
            status: Campaign status codes to include.
            type_: Campaign type codes to include.

        Returns:
            List of raw campaign dicts from the API.
        """
        params: dict[str, Any] = {}
        if status:
            params['status'] = status
        if type_:
            params['type'] = type_
        result = self._http.get(EP_CAMPAIGN_LIST, params=params)
        return result if isinstance(result, list) else []

    def get_campaign(self, campaign_id: int) -> dict | None:
        """Retrieve a single campaign by ID.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            Campaign dict if found, None otherwise.
        """
        campaigns = self.list_campaigns()
        for c in campaigns:
            if c.get('advertId') == campaign_id:
                return c
        return None

    def get_eligible_subjects(self) -> list[dict]:
        """Retrieve subjects eligible for campaign creation.

        Returns:
            List of subject dicts.
        """
        result = self._http.get(EP_ELIGIBLE_SUBJECTS)
        return result if isinstance(result, list) else []

    def get_eligible_items(self, subject_id: int) -> list[dict]:
        """Retrieve product cards eligible for a given subject.

        Args:
            subject_id: Subject category ID.

        Returns:
            List of product card dicts.
        """
        result = self._http.get(
            EP_ELIGIBLE_ITEMS, params={'id': subject_id}
        )
        return result if isinstance(result, list) else []

    def get_balance(self) -> dict:
        """Retrieve account-level balance.

        Returns:
            Balance dict with balance, net, bonus fields.
        """
        result = self._http.get(EP_ACCOUNT_BALANCE)
        return result if isinstance(result, dict) else {}

    def get_budget(self, campaign_id: int) -> dict:
        """Retrieve budget for a specific campaign.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            Budget dict with total, dailyBudget, balance fields.
        """
        result = self._http.get(
            EP_CAMPAIGN_BUDGET, params={'id': campaign_id}
        )
        return result if isinstance(result, dict) else {}

    def get_campaign_stats(
            self,
            campaign_ids: list[int],
            date_from: str,
            date_to: str,
    ) -> list[dict]:
        """Retrieve campaign statistics for a date range.

        Args:
            campaign_ids: Campaign IDs to query.
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            List of campaign stats dicts.
        """
        body = [
            {'id': cid, 'dates': [date_from, date_to]}
            for cid in campaign_ids
        ]
        result = self._http.post(EP_CAMPAIGN_FULLSTATS, json_body=body)
        return result if isinstance(result, list) else []

    def get_recommended_bids(self, campaign_id: int) -> list[dict]:
        """Retrieve recommended CPM bids for a campaign.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            List of bid recommendation dicts.
        """
        result = self._http.get(
            EP_RECOMMENDED_BID, params={'id': campaign_id}
        )
        return result if isinstance(result, list) else []

    def get_active_clusters(self, campaign_id: int) -> dict:
        """Retrieve active search clusters for a campaign.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            Response dict containing active cluster data.
        """
        result = self._http.get(
            EP_CLUSTER_ACTIVE, params={'id': campaign_id}
        )
        return result if isinstance(result, dict) else {}

    def get_all_clusters(self, campaign_id: int) -> dict:
        """Retrieve all search clusters and bids for a campaign.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            Response dict containing all cluster data.
        """
        result = self._http.get(
            EP_CLUSTER_ALL, params={'id': campaign_id}
        )
        return result if isinstance(result, dict) else {}

    def get_cluster_stats(self, campaign_id: int) -> dict:
        """Retrieve search cluster statistics for a campaign.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            Response dict containing cluster statistics.
        """
        result = self._http.get(
            EP_CLUSTER_STATS, params={'id': campaign_id}
        )
        return result if isinstance(result, dict) else {}

    # ── Write operations ──────────────────────────────────────────────

    def start_campaign(self, campaign_id: int) -> None:
        """Start a campaign.

        Args:
            campaign_id: Target campaign identifier.
        """
        self._http.get(EP_CAMPAIGN_START, params={'id': campaign_id})

    def pause_campaign(self, campaign_id: int) -> None:
        """Pause a running campaign.

        Args:
            campaign_id: Target campaign identifier.
        """
        self._http.get(EP_CAMPAIGN_PAUSE, params={'id': campaign_id})

    def stop_campaign(self, campaign_id: int) -> None:
        """Stop a campaign (archive it).

        Args:
            campaign_id: Target campaign identifier.
        """
        self._http.get(EP_CAMPAIGN_STOP, params={'id': campaign_id})

    def rename_campaign(self, campaign_id: int, name: str) -> None:
        """Rename a campaign.

        Args:
            campaign_id: Target campaign identifier.
            name: New campaign name.
        """
        self._http.post(
            EP_CAMPAIGN_RENAME,
            json_body={'advertId': campaign_id, 'name': name},
        )

    def delete_campaign(self, campaign_id: int) -> None:
        """Delete a campaign.

        Args:
            campaign_id: Target campaign identifier.
        """
        self._http.delete(
            EP_CAMPAIGN_LIST, params={'ids': [campaign_id]}
        )

    def create_campaign(self, payload: dict) -> dict:
        """Create a new campaign.

        Args:
            payload: Campaign creation parameters dict.

        Returns:
            New campaign data dict from the API.
        """
        result = self._http.post(EP_CAMPAIGN_CREATE, json_body=payload)
        return result if isinstance(result, dict) else {}

    def add_items(self, campaign_id: int, nm_ids: list[int]) -> None:
        """Add product items to a campaign.

        Args:
            campaign_id: Target campaign identifier.
            nm_ids: List of product nomenclature IDs to add.
        """
        self._http.post(
            EP_CAMPAIGN_ITEMS,
            json_body={'advertId': campaign_id, 'nms': nm_ids},
        )

    def remove_items(self, campaign_id: int, nm_ids: list[int]) -> None:
        """Remove product items from a campaign.

        Args:
            campaign_id: Target campaign identifier.
            nm_ids: List of product nomenclature IDs to remove.
        """
        self._http.delete(
            EP_CAMPAIGN_ITEMS,
            json_body={'advertId': campaign_id, 'nms': nm_ids},
        )

    def set_placements(self, campaign_id: int, payload: dict) -> None:
        """Update placement configuration for a campaign.

        Args:
            campaign_id: Target campaign identifier.
            payload: Placement params payload (from PlacementConfig.to_api).
        """
        self._http.post(EP_CAMPAIGN_PLACEMENTS, json_body=payload)

    def deposit_budget(self, campaign_id: int, amount: int) -> None:
        """Deposit funds into a campaign budget.

        Args:
            campaign_id: Target campaign identifier.
            amount: Amount to deposit in kopecks.
        """
        self._http.post(
            EP_BUDGET_DEPOSIT,
            json_body={
                'sum': amount,
                'advertId': campaign_id,
                'type': _DEPOSIT_TYPE_ADD,
            },
        )

    def set_item_bid(self, payload: dict) -> None:
        """Set a CPM bid for a campaign item.

        Args:
            payload: Bid payload dict (from BidMutation.to_api).
        """
        self._http.post(EP_BID_SET, json_body=payload)
