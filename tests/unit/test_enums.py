"""Tests for wb.domain.enums module."""

import pytest

from wb.domain.enums import (
    CampaignStatus,
    CampaignType,
    OutputFormat,
    PaymentType,
)


class TestCampaignStatus:
    """Tests for CampaignStatus enum."""

    @pytest.mark.parametrize(
        ('member', 'value'),
        [
            ('DELETED', -1),
            ('READY', 4),
            ('ARCHIVED', 7),
            ('DECLINED', 8),
            ('RUNNING', 9),
            ('PAUSED', 11),
        ],
    )
    def test_member_values(self, member: str, value: int) -> None:
        assert CampaignStatus[member] == value

    @pytest.mark.parametrize('value', [-1, 4, 7, 8, 9, 11])
    def test_construct_from_value(self, value: int) -> None:
        status = CampaignStatus(value)
        assert status.value == value


class TestCampaignType:
    """Tests for CampaignType enum."""

    @pytest.mark.parametrize(
        ('member', 'value'),
        [
            ('SEARCH_PLUS_CATALOG', 6),
            ('AUTO', 8),
            ('STANDARD', 9),
        ],
    )
    def test_member_values(self, member: str, value: int) -> None:
        assert CampaignType[member] == value

    @pytest.mark.parametrize('value', [6, 8, 9])
    def test_construct_from_value(self, value: int) -> None:
        campaign_type = CampaignType(value)
        assert campaign_type.value == value


class TestPaymentType:
    """Tests for PaymentType enum."""

    def test_cpm_value(self) -> None:
        assert PaymentType.CPM.value == 'cpm'

    def test_cpc_value(self) -> None:
        assert PaymentType.CPC.value == 'cpc'

    @pytest.mark.parametrize('value', ['cpm', 'cpc'])
    def test_construct_from_value(self, value: str) -> None:
        payment = PaymentType(value)
        assert payment.value == value

    def test_values_are_exactly_cpm_and_cpc(self) -> None:
        values = {m.value for m in PaymentType}
        assert values == {'cpm', 'cpc'}


class TestOutputFormat:
    """Tests for OutputFormat enum."""

    def test_has_table(self) -> None:
        assert OutputFormat.TABLE.value == 'table'

    def test_has_json(self) -> None:
        assert OutputFormat.JSON.value == 'json'

    def test_has_quiet(self) -> None:
        assert OutputFormat.QUIET.value == 'quiet'

    @pytest.mark.parametrize('value', ['table', 'json', 'quiet'])
    def test_construct_from_value(self, value: str) -> None:
        fmt = OutputFormat(value)
        assert fmt.value == value
