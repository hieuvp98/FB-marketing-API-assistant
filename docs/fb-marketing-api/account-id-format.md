# Facebook Account ID Format

## Quy tắc quan trọng

| Table | Field | Format | Ví dụ |
|-------|-------|--------|-------|
| `fb_ad_account` | `id` / `account_id` | **Có** `act_` prefix | `act_893080633703946` |
| `fb_ad_account` | `account_id` (khi gọi API) | Có `act_` prefix | `act_893080633703946` |
| `fb_campaign` | `account_id` | **Raw numeric** | `893080633703946` |
| `fb_adset` | `account_id` | **Raw numeric** | `893080633703946` |
| `fb_ad` | `account_id` | **Raw numeric** | `893080633703946` |
| `SyncHistory` | `dataId` | **Có** `act_` prefix | `act_893080633703946` |

## Khi JOIN các tables

```sql
-- SAI: campaign.account_id KHÔNG có act_ prefix
SELECT * FROM fb_campaign c
JOIN fb_ad_account a ON c.account_id = a.account_id;

-- ĐÚNG: so sánh numeric, bỏ act_ prefix
SELECT * FROM fb_campaign c
JOIN fb_ad_account a ON c.account_id = REPLACE(a.account_id, 'act_', '');
```

## Khi gọi Facebook API

```bash
# API luôn cần act_ prefix
GET /act_893080633703946/campaigns

# KHÔNG dùng
GET /893080633703946/campaigns
```

## Khi lưu vào DB

```java
// Java: lưu raw numeric, bỏ act_ prefix
String rawId = apiResponse.getAccountId().replace("act_", "");
campaign.setAccountId(rawId);
```

## Liên quan
- [Facebook Graph API](facebook-graph-api.md)
- [Insights API Queries](insights-queries.md)
