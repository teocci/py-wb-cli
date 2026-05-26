"""Domain models for WB Finance API — sales-reports and acquiring summaries.

Only the two ``list`` (summary) responses get typed dataclasses here.
Detail rows from the ``detailed*`` endpoints carry ~90 fields per row
and are passed through as raw ``dict`` to preserve lossless WB field
parity (matches the I-21 ``wb report sales/orders`` pattern). Adding new
WB fields then doesn't require a dataclass migration.

Money amounts are kept as strings exactly as WB sends them — they are
fixed-precision decimal values where float conversion would introduce
rounding error.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ['SalesReportSummary', 'AcquiringReportSummary']


@dataclass(slots=True)
class SalesReportSummary:
    """Header row from ``/api/finance/v1/sales-reports/list``.

    One per WB-generated settlement statement. Money fields are
    strings (preserve fixed-precision); ``report_type`` is the
    1/2/3 enum (general / purchase / Georgia).

    Attributes:
        report_id: WB report identifier (int64; preserved natively).
        seller_finance_name: Seller legal name on the statement.
        date_from: Reporting period start (YYYY-MM-DD).
        date_to: Reporting period end (YYYY-MM-DD).
        create_date: Date WB generated the report (YYYY-MM-DD).
        currency: Three-letter currency code.
        report_type: ``1`` general, ``2`` purchase, ``3`` purchase-Georgia.
        retail_amount_sum: Total sales in the reporting period.
        for_pay_sum: Net revenue (what WB pays the seller).
        avg_sale_percent: Agreed discount percent (%).
        delivery_service_sum: Logistics cost.
        paid_storage_sum: Storage cost.
        paid_acceptance_sum: Acceptance cost.
        deduction_sum: Other deductions and payments.
        penalty_sum: Total penalties.
        additional_payment_sum: WB fee adjustment.
        cashback_amount_sum: Deducted for loyalty program rewards.
        cashback_discount_sum: Loyalty program discount compensation.
        cashback_commission_change_sum: Loyalty program cost.
        payment_schedule: One-time payment period change.
        bank_payment_sum: Total bank payment.
    """

    report_id: int
    seller_finance_name: str
    date_from: str
    date_to: str
    create_date: str
    currency: str
    report_type: int
    retail_amount_sum: str
    for_pay_sum: str
    avg_sale_percent: float
    delivery_service_sum: str
    paid_storage_sum: str
    paid_acceptance_sum: str
    deduction_sum: str
    penalty_sum: str
    additional_payment_sum: str
    cashback_amount_sum: str
    cashback_discount_sum: str
    cashback_commission_change_sum: str
    payment_schedule: str
    bank_payment_sum: str

    @classmethod
    def from_api(cls, data: dict) -> SalesReportSummary:
        """Build from a raw entry in the ``/sales-reports/list`` response.

        Args:
            data: Raw dict from the WB API.
        """
        return cls(
            report_id=int(data.get('reportId', 0)),
            seller_finance_name=data.get('sellerFinanceName', ''),
            date_from=data.get('dateFrom', ''),
            date_to=data.get('dateTo', ''),
            create_date=data.get('createDate', ''),
            currency=data.get('currency', ''),
            report_type=int(data.get('reportType', 0)),
            retail_amount_sum=str(data.get('retailAmountSum', '0')),
            for_pay_sum=str(data.get('forPaySum', '0')),
            avg_sale_percent=float(data.get('avgSalePercent', 0) or 0),
            delivery_service_sum=str(data.get('deliveryServiceSum', '0')),
            paid_storage_sum=str(data.get('paidStorageSum', '0')),
            paid_acceptance_sum=str(data.get('paidAcceptanceSum', '0')),
            deduction_sum=str(data.get('deductionSum', '0')),
            penalty_sum=str(data.get('penaltySum', '0')),
            additional_payment_sum=str(data.get('additionalPaymentSum', '0')),
            cashback_amount_sum=str(data.get('cashbackAmountSum', '0')),
            cashback_discount_sum=str(data.get('cashbackDiscountSum', '0')),
            cashback_commission_change_sum=str(
                data.get('cashbackCommissionChangeSum', '0'),
            ),
            payment_schedule=str(data.get('paymentSchedule', '0')),
            bank_payment_sum=str(data.get('bankPaymentSum', '0')),
        )


@dataclass(slots=True)
class AcquiringReportSummary:
    """Header row from ``/api/finance/v1/acquiring/list``.

    Attributes:
        report_id: WB report identifier (int64; preserved natively).
        seller_finance_name: Seller legal name on the statement.
        date_from: Reporting period start (YYYY-MM-DD).
        date_to: Reporting period end (YYYY-MM-DD).
        create_date: Date WB generated the report (YYYY-MM-DD).
        currency: Three-letter currency code.
        acquiring_fee_sum: Total acquiring (card-processing) expenses.
        acquiring_fee_vat_sum: VAT portion of the acquiring fee.
    """

    report_id: int
    seller_finance_name: str
    date_from: str
    date_to: str
    create_date: str
    currency: str
    acquiring_fee_sum: str
    acquiring_fee_vat_sum: str

    @classmethod
    def from_api(cls, data: dict) -> AcquiringReportSummary:
        """Build from a raw entry in the ``/acquiring/list`` response.

        Args:
            data: Raw dict from the WB API.
        """
        return cls(
            report_id=int(data.get('reportId', 0)),
            seller_finance_name=data.get('sellerFinanceName', ''),
            date_from=data.get('dateFrom', ''),
            date_to=data.get('dateTo', ''),
            create_date=data.get('createDate', ''),
            currency=data.get('currency', ''),
            acquiring_fee_sum=str(data.get('acquiringFeeSum', '0')),
            acquiring_fee_vat_sum=str(data.get('acquiringFeeVatSum', '0')),
        )
