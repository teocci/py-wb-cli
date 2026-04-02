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
    EP_CAMPAIGN_DELETE,
    EP_CAMPAIGN_FULLSTATS,
    EP_CAMPAIGN_INFO,
    EP_CAMPAIGN_ITEMS,
    EP_CAMPAIGN_PAUSE,
    EP_CAMPAIGN_PLACEMENTS,
    EP_CAMPAIGN_RENAME,
    EP_CAMPAIGN_START,
    EP_CAMPAIGN_STOP,
    EP_ELIGIBLE_ITEMS,
    EP_ELIGIBLE_SUBJECTS,
    EP_NQ_DEL_BIDS,
    EP_NQ_GET_BIDS,
    EP_NQ_GET_MINUS,
    EP_NQ_LIST,
    EP_NQ_SET_BIDS,
    EP_NQ_SET_MINUS,
    EP_NQ_STATS,
    EP_NQ_STATS_DAILY,
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
            ids: list[int] | None = None,
    ) -> list[dict]:
        """List campaigns via /api/advert/v2/adverts.

        Args:
            status: Campaign status codes to include.
            type_: Campaign type codes to include.
            ids: Specific campaign IDs to fetch (max 50).

        Returns:
            List of raw campaign dicts from the API.
        """
        params: dict[str, Any] = {}
        if ids:
            params['ids'] = ','.join(str(i) for i in ids)
        if status:
            params['statuses'] = ','.join(str(s) for s in status)
        if type_:
            params['payment_type'] = type_[0] if type_ else None
        result = self._http.get(EP_CAMPAIGN_INFO, params=params)
        adverts = result.get('adverts', []) if isinstance(result, dict) else []
        return adverts if isinstance(adverts, list) else []

    def get_campaign(self, campaign_id: int) -> dict | None:
        """Retrieve a single campaign by ID.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            Campaign dict if found, None otherwise.
        """
        campaigns = self.list_campaigns(ids=[campaign_id])
        for c in campaigns:
            if c.get('id') == campaign_id:
                return c
        return None

    def get_eligible_subjects(self) -> list[dict]:
        """Retrieve subjects eligible for campaign creation.

        Returns:
            List of subject dicts.
        """
        result = self._http.get(EP_ELIGIBLE_SUBJECTS)
        return result if isinstance(result, list) else []

    def get_eligible_items(self, subject_ids: list[int]) -> list[dict]:
        """Retrieve product cards for given subjects via POST.

        Args:
            subject_ids: Subject category IDs to query.

        Returns:
            List of product card dicts with title, nm, subjectId.
        """
        result = self._http.post(
            EP_ELIGIBLE_ITEMS, json_body=subject_ids,
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
        """Retrieve campaign statistics via GET /adv/v3/fullstats.

        Args:
            campaign_ids: Campaign IDs to query (max 50).
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            List of campaign stats dicts.
        """
        params = {
            'ids': ','.join(str(i) for i in campaign_ids),
            'beginDate': date_from,
            'endDate': date_to,
        }
        result = self._http.get(EP_CAMPAIGN_FULLSTATS, params=params)
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

    def get_cluster_list(
            self, items: list[dict],
    ) -> dict:
        """Retrieve active/inactive cluster lists via POST normquery/list.

        Args:
            items: List of {advertId, nmId} dicts (max 100).

        Returns:
            Response dict with items[].normQueries.active/excluded.
        """
        result = self._http.post(
            EP_NQ_LIST, json_body={'items': items}
        )
        return result if isinstance(result, dict) else {}

    def get_cluster_bids(
            self, items: list[dict],
    ) -> dict:
        """Retrieve cluster bids via POST normquery/get-bids.

        Args:
            items: List of {advert_id, nm_id} dicts (max 100).

        Returns:
            Response dict with bids[].
        """
        result = self._http.post(
            EP_NQ_GET_BIDS, json_body={'items': items}
        )
        return result if isinstance(result, dict) else {}

    def get_cluster_stats(
            self,
            date_from: str,
            date_to: str,
            items: list[dict],
    ) -> dict:
        """Retrieve cluster stats via POST normquery/stats.

        Args:
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).
            items: List of {advert_id, nm_id} dicts (max 100).

        Returns:
            Response dict with stats[].stats[].
        """
        result = self._http.post(
            EP_NQ_STATS,
            json_body={'from': date_from, 'to': date_to, 'items': items},
        )
        return result if isinstance(result, dict) else {}

    def get_cluster_stats_daily(
            self,
            date_from: str,
            date_to: str,
            items: list[dict],
    ) -> dict:
        """Retrieve daily cluster stats via POST normquery/stats v1.

        Args:
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).
            items: List of {advertId, nmId} dicts (max 100).

        Returns:
            Response dict with items[].dailyStats[].
        """
        result = self._http.post(
            EP_NQ_STATS_DAILY,
            json_body={'from': date_from, 'to': date_to, 'items': items},
        )
        return result if isinstance(result, dict) else {}

    def get_minus_phrases(
            self, items: list[dict],
    ) -> dict:
        """Retrieve minus phrases via POST normquery/get-minus.

        Args:
            items: List of {advert_id, nm_id} dicts (max 100).

        Returns:
            Response dict with items[].norm_queries[].
        """
        result = self._http.post(
            EP_NQ_GET_MINUS, json_body={'items': items}
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
        """Delete a campaign via GET /adv/v0/delete.

        Args:
            campaign_id: Target campaign identifier.
        """
        self._http.get(
            EP_CAMPAIGN_DELETE, params={'id': campaign_id}
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
        self._http.put(
            EP_CAMPAIGN_PLACEMENTS,
            json_body={'placements': [payload]},
        )

    def deposit_budget(self, campaign_id: int, amount: int) -> None:
        """Deposit funds into a campaign budget.

        Args:
            campaign_id: Target campaign identifier.
            amount: Amount to deposit.
        """
        self._http.post(
            EP_BUDGET_DEPOSIT,
            params={'id': campaign_id},
            json_body={
                'sum': amount,
                'type': _DEPOSIT_TYPE_ADD,
                'return': True,
            },
        )

    def set_item_bid(self, payload: dict) -> None:
        """Set a bid for a campaign item.

        Args:
            payload: Bid payload dict (from BidMutation.to_api).
        """
        self._http.patch(EP_BID_SET, json_body={'bids': [payload]})

    def set_cluster_bids(self, bids: list[dict]) -> None:
        """Set bids for search clusters via POST normquery/bids.

        Args:
            bids: List of bid dicts (max 100), each with
                  advert_id, nm_id, norm_query, bid.
        """
        self._http.post(EP_NQ_SET_BIDS, json_body={'bids': bids})

    def delete_cluster_bids(self, bids: list[dict]) -> None:
        """Delete bids from search clusters via DELETE normquery/bids.

        Args:
            bids: List of bid dicts (max 100), each with
                  advert_id, nm_id, norm_query, bid.
        """
        self._http.delete(EP_NQ_DEL_BIDS, json_body={'bids': bids})

    def set_minus_phrases(self, payload: dict) -> None:
        """Set or clear minus phrases via POST normquery/set-minus.

        Args:
            payload: Dict with advert_id, nm_id, norm_queries.
                     Empty norm_queries list clears all minus phrases.
        """
        self._http.post(EP_NQ_SET_MINUS, json_body=payload)
