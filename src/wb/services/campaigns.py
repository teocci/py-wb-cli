"""Campaign-related use-cases."""

from __future__ import annotations

from wb.client.promotion import PromotionClient
from wb.core.exceptions import ValidationError, WbCliError
from wb.domain.enums import CampaignStatus, CampaignType
from wb.domain.models import (
    Campaign,
    CampaignCreate,
    MutationResult,
    PlacementConfig,
    ProductCard,
)

__all__ = ['CampaignService']


class CampaignService:
    """Orchestrates campaign read operations.

    Attributes:
        client: Promotion API client.
    """

    def __init__(self, client: PromotionClient) -> None:
        self._client = client

    def list_campaigns(
            self,
            status: CampaignStatus | None = None,
            type_: CampaignType | None = None,
    ) -> list[Campaign]:
        """List campaigns with optional filtering.

        Args:
            status: Filter by campaign status.
            type_: Filter by campaign type.

        Returns:
            List of Campaign domain objects.
        """
        status_filter = [status.value] if status else None
        type_filter = [type_.value] if type_ else None
        raw = self._client.list_campaigns(
            status=status_filter, type_=type_filter,
        )
        return [Campaign.from_api(c) for c in raw]

    def get_campaign(self, campaign_id: int) -> Campaign:
        """Retrieve a single campaign by ID.

        Args:
            campaign_id: Target campaign identifier.

        Returns:
            Campaign domain object.

        Raises:
            ValidationError: If campaign not found.
        """
        raw = self._client.get_campaign(campaign_id)
        if raw is None:
            raise ValidationError(f'Campaign {campaign_id} not found')
        return Campaign.from_api(raw)

    def get_eligible_subjects(self) -> list[dict]:
        """Retrieve subjects eligible for campaign creation.

        Returns:
            List of subject dicts (id, name).
        """
        return self._client.get_eligible_subjects()

    def get_eligible_items(self, subject_id: int) -> list[ProductCard]:
        """Retrieve product cards eligible for a given subject.

        Args:
            subject_id: Subject category ID.

        Returns:
            List of ProductCard domain objects.
        """
        raw = self._client.get_eligible_items([subject_id])
        return [ProductCard.from_api(item) for item in raw]

    def create_campaign(
            self,
            params: CampaignCreate,
            dry_run: bool = False,
    ) -> MutationResult:
        """Create a new campaign.

        Args:
            params: Campaign creation parameters.
            dry_run: If True, plan without executing.

        Returns:
            MutationResult with the new campaign ID on success.
        """
        action = f'create campaign "{params.name}" bid_type={params.bid_type}'
        if dry_run:
            return MutationResult(
                success=True, action=action, target_id='new',
                dry_run=True, message='Would create campaign',
            )
        result = self._client.create_campaign(params.to_api())
        new_id = str(result.get('advertId', ''))
        return MutationResult(
            success=True, action=action, target_id=new_id,
            message=f'Campaign created with ID {new_id}',
        )

    def start_campaign(
            self, campaign_id: int, dry_run: bool = False,
    ) -> MutationResult:
        """Start a campaign.

        Args:
            campaign_id: Target campaign identifier.
            dry_run: If True, plan without executing.

        Returns:
            MutationResult describing the outcome.
        """
        action = f'start campaign {campaign_id}'
        if dry_run:
            return MutationResult(
                success=True, action=action, target_id=str(campaign_id),
                dry_run=True, message='Would start campaign',
            )
        self._client.start_campaign(campaign_id)
        return MutationResult(
            success=True, action=action, target_id=str(campaign_id),
            message='Campaign started',
        )

    def pause_campaign(
            self, campaign_id: int, dry_run: bool = False,
    ) -> MutationResult:
        """Pause a running campaign.

        Args:
            campaign_id: Target campaign identifier.
            dry_run: If True, plan without executing.

        Returns:
            MutationResult describing the outcome.
        """
        action = f'pause campaign {campaign_id}'
        if dry_run:
            return MutationResult(
                success=True, action=action, target_id=str(campaign_id),
                dry_run=True, message='Would pause campaign',
            )
        self._client.pause_campaign(campaign_id)
        return MutationResult(
            success=True, action=action, target_id=str(campaign_id),
            message='Campaign paused',
        )

    def stop_campaign(
            self, campaign_id: int, dry_run: bool = False,
    ) -> MutationResult:
        """Stop (archive) a campaign.

        Args:
            campaign_id: Target campaign identifier.
            dry_run: If True, plan without executing.

        Returns:
            MutationResult describing the outcome.
        """
        action = f'stop campaign {campaign_id}'
        if dry_run:
            return MutationResult(
                success=True, action=action, target_id=str(campaign_id),
                dry_run=True, message='Would stop campaign',
            )
        self._client.stop_campaign(campaign_id)
        return MutationResult(
            success=True, action=action, target_id=str(campaign_id),
            message='Campaign stopped',
        )

    def rename_campaign(
            self,
            campaign_id: int,
            name: str,
            dry_run: bool = False,
    ) -> MutationResult:
        """Rename a campaign.

        Args:
            campaign_id: Target campaign identifier.
            name: New campaign name.
            dry_run: If True, plan without executing.

        Returns:
            MutationResult describing the outcome.
        """
        action = f'rename campaign {campaign_id} to "{name}"'
        if dry_run:
            return MutationResult(
                success=True, action=action, target_id=str(campaign_id),
                dry_run=True, message='Would rename campaign',
            )
        self._client.rename_campaign(campaign_id, name)
        return MutationResult(
            success=True, action=action, target_id=str(campaign_id),
            message=f'Campaign renamed to "{name}"',
        )

    def delete_campaign(
            self, campaign_id: int, dry_run: bool = False,
    ) -> MutationResult:
        """Delete a campaign.

        Args:
            campaign_id: Target campaign identifier.
            dry_run: If True, plan without executing.

        Returns:
            MutationResult describing the outcome.
        """
        action = f'delete campaign {campaign_id}'
        if dry_run:
            return MutationResult(
                success=True, action=action, target_id=str(campaign_id),
                dry_run=True, message='Would delete campaign',
            )
        self._client.delete_campaign(campaign_id)
        return MutationResult(
            success=True, action=action, target_id=str(campaign_id),
            message='Campaign deleted',
        )

    def start_campaigns(
            self,
            campaign_ids: list[int],
            dry_run: bool = False,
    ) -> list[MutationResult]:
        """Start multiple campaigns, collecting per-campaign results.

        Calls start_campaign for each ID. Failures for individual campaigns
        are captured in the result list without aborting the rest.

        Args:
            campaign_ids: Target campaign identifiers.
            dry_run: If True, plan without executing.

        Returns:
            List of MutationResult, one per campaign_id.
        """
        results: list[MutationResult] = []
        for cid in campaign_ids:
            try:
                results.append(self.start_campaign(cid, dry_run=dry_run))
            except WbCliError as exc:
                results.append(MutationResult(
                    success=False, action=f'start campaign {cid}',
                    target_id=str(cid), message=str(exc),
                ))
        return results

    def pause_campaigns(
            self,
            campaign_ids: list[int],
            dry_run: bool = False,
    ) -> list[MutationResult]:
        """Pause multiple campaigns, collecting per-campaign results.

        Args:
            campaign_ids: Target campaign identifiers.
            dry_run: If True, plan without executing.

        Returns:
            List of MutationResult, one per campaign_id.
        """
        results: list[MutationResult] = []
        for cid in campaign_ids:
            try:
                results.append(self.pause_campaign(cid, dry_run=dry_run))
            except WbCliError as exc:
                results.append(MutationResult(
                    success=False, action=f'pause campaign {cid}',
                    target_id=str(cid), message=str(exc),
                ))
        return results

    def stop_campaigns(
            self,
            campaign_ids: list[int],
            dry_run: bool = False,
    ) -> list[MutationResult]:
        """Stop multiple campaigns, collecting per-campaign results.

        Args:
            campaign_ids: Target campaign identifiers.
            dry_run: If True, plan without executing.

        Returns:
            List of MutationResult, one per campaign_id.
        """
        results: list[MutationResult] = []
        for cid in campaign_ids:
            try:
                results.append(self.stop_campaign(cid, dry_run=dry_run))
            except WbCliError as exc:
                results.append(MutationResult(
                    success=False, action=f'stop campaign {cid}',
                    target_id=str(cid), message=str(exc),
                ))
        return results

    def delete_campaigns(
            self,
            campaign_ids: list[int],
            dry_run: bool = False,
    ) -> list[MutationResult]:
        """Delete multiple campaigns, collecting per-campaign results.

        Args:
            campaign_ids: Target campaign identifiers.
            dry_run: If True, plan without executing.

        Returns:
            List of MutationResult, one per campaign_id.
        """
        results: list[MutationResult] = []
        for cid in campaign_ids:
            try:
                results.append(self.delete_campaign(cid, dry_run=dry_run))
            except WbCliError as exc:
                results.append(MutationResult(
                    success=False, action=f'delete campaign {cid}',
                    target_id=str(cid), message=str(exc),
                ))
        return results

    def add_items(
            self,
            campaign_id: int,
            nm_ids: list[int],
            dry_run: bool = False,
    ) -> MutationResult:
        """Add product items to a campaign.

        Args:
            campaign_id: Target campaign identifier.
            nm_ids: Product nomenclature IDs to add.
            dry_run: If True, plan without executing.

        Returns:
            MutationResult describing the outcome.
        """
        action = f'add {len(nm_ids)} item(s) to campaign {campaign_id}'
        if dry_run:
            return MutationResult(
                success=True, action=action, target_id=str(campaign_id),
                dry_run=True, message=f'Would add items: {nm_ids}',
            )
        self._client.add_items(campaign_id, nm_ids)
        return MutationResult(
            success=True, action=action, target_id=str(campaign_id),
            message=f'Added {len(nm_ids)} item(s)',
        )

    def remove_items(
            self,
            campaign_id: int,
            nm_ids: list[int],
            dry_run: bool = False,
    ) -> MutationResult:
        """Remove product items from a campaign.

        Args:
            campaign_id: Target campaign identifier.
            nm_ids: Product nomenclature IDs to remove.
            dry_run: If True, plan without executing.

        Returns:
            MutationResult describing the outcome.
        """
        action = f'remove {len(nm_ids)} item(s) from campaign {campaign_id}'
        if dry_run:
            return MutationResult(
                success=True, action=action, target_id=str(campaign_id),
                dry_run=True, message=f'Would remove items: {nm_ids}',
            )
        self._client.remove_items(campaign_id, nm_ids)
        return MutationResult(
            success=True, action=action, target_id=str(campaign_id),
            message=f'Removed {len(nm_ids)} item(s)',
        )

    def set_placements(
            self,
            campaign_id: int,
            config: PlacementConfig,
            dry_run: bool = False,
    ) -> MutationResult:
        """Set placement configuration for a campaign.

        Args:
            campaign_id: Target campaign identifier.
            config: Placement configuration to apply.
            dry_run: If True, plan without executing.

        Returns:
            MutationResult describing the outcome.
        """
        desc = (
            f'search={config.search_enabled}, '
            f'recommendations={config.recommendations_enabled}'
        )
        action = f'set placements for campaign {campaign_id}: {desc}'
        if dry_run:
            return MutationResult(
                success=True, action=action, target_id=str(campaign_id),
                dry_run=True, message='Would update placements',
            )
        self._client.set_placements(campaign_id, config.to_api(campaign_id))
        return MutationResult(
            success=True, action=action, target_id=str(campaign_id),
            message='Placements updated',
        )
