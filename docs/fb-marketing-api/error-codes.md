# Facebook API Error Codes

## Error Code Table

| Code | Ý nghĩa | Xử lý |
|------|---------|-------|
| **1** | General error / bad request | Halve `limit` param và retry |
| **2** | Temporary server error | Retry up to `max-retry-for-fb-errors` (default 8) |
| **960** | Timeout / query quá chậm | Retry (same as code 2) |
| **80004** | Rate limited | Cooldown 60 phút, ghi vào SyncHistory |
| **400** | Bad request / token expired | Không retry, fail ngay |
| **403** | Forbidden / token disconnected | Không retry, fail ngay |

## Chi tiết xử lý

### Error Code 1 — General Error

Thường gặp khi request quá lớn hoặc params sai.

**Xử lý:**
- Giảm `limit` xuống một nửa
- Retry request
- Nếu vẫn lỗi, ghi vào SyncHistory

### Error Code 2 — Temporary Error

Lỗi tạm thời từ server Facebook.

**Xử lý:**
- Retry với exponential backoff
- Tối đa 8 lần (configurable qua `max-retry-for-fb-errors`)
- Nếu hết retry vẫn lỗi, ghi vào SyncHistory

### Error Code 960 — Timeout

Query quá phức tạp hoặc timeout.

**Xử lý:**
- Giống code 2: retry up to 8 lần
- **Prevention**: Insight prefetch chỉ gửi tối đa 12 ad accounts per batch
- Dùng minimal fields (spend, actions) cho prefetch

### Error Code 80004 — Rate Limited

Vượt quá rate limit của Facebook.

**Xử lý:**
- Bật cooldown: `fbRateLimitCoolDownMinutes = 60`
- Trong cooldown, tất cả request bị block
- Ghi vào SyncHistory để tracking

### Error 400/403 — Token Issues

Token bị expired hoặc bị disconnect.

**Xử lý:**
- Không retry
- Fail ngay lập tức
- Ghi vào SyncHistory
- User cần refresh token

## Config trong Nemi

```yaml
facebook:
  sync-data:
    max-retry-for-fb-errors: 8
    fb-rate-limit-cool-down-minutes: 60
```

## Related
- [Facebook Graph API](facebook-graph-api.md)
- [Insights API Queries](insights-queries.md)
