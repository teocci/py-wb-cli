# Phase 4 — Analytics Bridge (v0.5.0)

**Date:** 2026-04-03 | **Tests:** 474 passed (+69)

## What Was Built

- `AnalyticsClient` (`client/analytics.py`): 12 methods — 3 sales funnel, 5 search report, 4 CSV report
- Domain models (`domain/analytics_models.py`): `ProductFunnelStats`, `FunnelHistoryDay`, `ProductFunnelHistory`, `SearchReportProduct`, `SearchReportGroup`, `SearchTextEntry`, `CsvReportStatus` + `ReportType`, `AggregationLevel` enums
- `AnalyticsService` (`services/analytics.py`): 12 service methods with validation
- `WbHttpClient.request_raw()`: binary download method for ZIP files
- `WB_ANALYTICS_TOKEN` env var + `_get_analytics_token()` priority chain
- 12 CLI commands: `wb analytics sales-funnel products|history|grouped`, `wb analytics search-report main|groups|details|search-texts|orders`, `wb analytics csv create|list|retry|download`
- Base URL: `seller-analytics-api.wildberries.ru` with separate analytics token (bit 2)
