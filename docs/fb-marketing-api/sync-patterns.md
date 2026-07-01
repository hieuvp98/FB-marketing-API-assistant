# Facebook Marketing API Sync Patterns

## PullDataHandler Pattern

Nemi platform dùng abstract handler pattern để sync data từ Facebook:

```
PullDataHandler (abstract)
  ├── AdAccountHandler
  ├── CampaignHandler
  ├── AdSetHandler
  ├── AdHandler
  ├── InsightHandler
  └── ...
```

### Flow

```
Kafka Message
    │
    ▼
PullDataHandler.process()
    │
    ├── validate request
    ├── gọi getBatch() → FB API
    ├── xử lý pagination (expand)
    ├── parse response
    └── batch upsert vào PostgreSQL
```

## Kafka Consumers

Các consumer trong nemi-worker-service:

| Consumer | Mô tả |
|----------|-------|
| `ad-account-insights-pull` | Insights cho ad accounts |
| `ad-objects-pull` | Campaigns, adsets, ads |
| `sync-changes` | Sync thay đổi |
| `daily-sync` | Sync hàng ngày |
| `business-pull` | Business accounts |
| `page-account-pull` | Pages |
| `campaign-product-link-pull` | Campaign-product links |
| `alert-rule-execute` | Execute alert rules |
| `alert-insight-prefetch` | Prefetch insights cho alerts |

## Alert System

4 alert handlers:

| Handler | Mô tả |
|---------|-------|
| `BalanceAlertHandler` | Kiểm tra số dư ad account |
| `CpaAlertHandler` | Kiểm tra CPA vượt ngưỡng |
| `BudgetSpikeAlertHandler` | Phát hiện budget spike bất thường |
| `TheftAlertHandler` | Phát hiện dấu hiệu bị hack |

### Budget Spike Detection

```sql
-- Dùng INNER JOIN LATERAL để tránh false positive
SELECT a.*, s.total_spend, ...
FROM fb_ad_account a
JOIN LATERAL (
    SELECT SUM(spend) as total_spend
    FROM fb_insights_ad_account
    WHERE account_id = a.account_id
      AND date >= NOW() - INTERVAL '1 day'
) s ON true
WHERE s.total_spend > a.daily_budget * 2;
```

## Quartz Jobs

| Job | Schedule | Mô tả |
|-----|----------|-------|
| `AlertRuleExecutorJob` | Every 5 minutes | Execute alert rules |
| `DailyCrawlerCurrencyRateJob` | Every hour | Crawl tỷ giá |

## Related
- [Facebook Graph API](facebook-graph-api.md)
- [Error Codes](error-codes.md)
- [Common Issues](common-issues.md)
