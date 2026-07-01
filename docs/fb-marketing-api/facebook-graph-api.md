# Facebook Graph API (Marketing API) Overview

## API Version

Hiện tại Nemi platform dùng **Facebook Graph API v23.0** cho worker sync production.
Riêng insights check script dùng **v24.0**.

Base URL: `https://graph.facebook.com/v23.0/`

## Authentication

Tất cả request đều cần access token:

```http
GET /v23.0/act_12345/insights
Authorization: Bearer {access_token}
```

Token có thể bị expired/disconnected → trả về error 400/403.

## Key Endpoints

| Endpoint | Mô tả |
|----------|-------|
| `GET /{fb_account}/adaccounts` | Danh sách ad accounts của FB account |
| `GET /act_{ad_account_id}/campaigns` | Campaigns trong ad account |
| `GET /{campaign_id}/adsets` | Ad sets trong campaign |
| `GET /{ad_set_id}/ads` | Ads trong ad set |
| `GET /act_{ad_account_id}/insights` | Thống kê chi tiêu, actions |

## Batch Requests

Dùng `FacebookWebClient.getBatch()` để gửi batch requests.
- Hỗ trợ pagination qua `expand()`
- Insight prefetch: tối đa **12 ad accounts** per FB account per batch
- Giới hạn này để tránh timeout (error 960)

## Rate Limiting

- Ad account level: mỗi ad account có rate limit riêng
- User level: tổng request trên tất cả ad accounts
- Khi bị rate limit: cooldown **60 phút** (`fbRateLimitCoolDownMinutes`)
- Trong thời gian cooldown, request mới bị block và ghi vào SyncHistory

## Field Selection

Luôn chỉ request fields cần thiết để tránh timeout.

### Insights minimal fields
```
fields=spend,actions
```

### Campaign fields
```
fields=id,name,status,objective,daily_budget,lifetime_budget,account_id
```

## Pagination

API trả về kết quả có phân trang qua cursor:

```json
{
  "data": [...],
  "paging": {
    "cursors": {
      "before": "xxx",
      "after": "yyy"
    },
    "next": "https://graph.facebook.com/v23.0/...&after=yyy"
  }
}
```

Dùng `expand()` trong `getBatch()` để tự động lấy hết pages.

## Sync Pattern

Nemi platform dùng pattern `PullDataHandler`:
1. Kafka consumer nhận message sync request
2. Gọi `FacebookWebClient.getBatch()` với endpoint + fields
3. Xử lý pagination
4. Batch upsert vào PostgreSQL

## Related
- [Error Codes](error-codes.md)
- [Insights API Queries](insights-queries.md)
- [Account ID Format](account-id-format.md)
