# Facebook Marketing API Common Issues

## 1. Insights API trả về lifetime total thay vì daily

**Vấn đề:** Dùng `since=...&until=...` nhưng API trả về tổng cho toàn bộ period.

**Nguyên nhân:** Facebook Graph API v23.0+ bỏ qua `since`/`until` params khi không có `time_increment`.

**Solution:** Luôn dùng `date_preset` hoặc `time_range` JSON object.

```bash
# Thay vì
since=2026-06-01&until=2026-06-07

# Dùng
date_preset=last_3d&time_increment=1
# Hoặc
time_range={"since":"2026-06-01","until":"2026-06-07"}&time_increment=1
```

## 2. Token expired/disconnected

**Vấn đề:** API trả về 400/403 — token không còn valid.

**Nguyên nhân:** 
- Token hết hạn (thường 60-90 ngày)
- User revoke app
- Password thay đổi

**Solution:**
- Không retry, fail ngay
- Ghi vào SyncHistory
- Gửi notification yêu cầu refresh token

## 3. Rate limit bị đạt

**Vấn đề:** Error 80004 — bị chặn vì quá nhiều request.

**Nguyên nhân:**
- Sync quá nhiều ad accounts cùng lúc
- Retry storm

**Solution:**
- Cooldown 60 phút
- Prefetch tối đa 12 ad accounts per batch
- Dùng minimal fields cho prefetch

## 4. Query insights timeout (error 960)

**Vấn đề:** Query insights bị timeout.

**Nguyên nhân:**
- Request quá nhiều fields
- Date range quá rộng
- Request quá nhiều ad accounts

**Solution:**
- Giảm fields xuống minimal (spend, actions)
- Chia nhỏ date range
- Retry (up to 8 lần)
- Giới hạn 12 ad accounts per batch

## 5. Campaign/adset/ad account_id mismatch

**Vấn đề:** JOIN campaign với ad account bị 0 rows.

**Nguyên nhân:** `campaign.account_id` là raw numeric (`893080633703946`) nhưng `ad_account.account_id` có `act_` prefix (`act_893080633703946`).

**Solution:** Strip `act_` prefix khi JOIN.

```sql
SELECT * FROM fb_campaign c
JOIN fb_ad_account a ON c.account_id = REPLACE(a.account_id, 'act_', '');
```

## 6. General error (error 1) khi query insights

**Vấn đề:** Error 1 — bad request.

**Nguyên nhân:** Request quá lớn (quá nhiều ad accounts hoặc date range quá rộng).

**Solution:** Halve `limit` param và retry.

## 7. Notification hiển thị sai FB account name

**Vấn đề:** Notification gửi lên hiển thị tên FB account khác với account thực tế.

**Nguyên nhân:** Một ad account được link với nhiều FB accounts — nếu query lấy sai account sẽ hiển thị sai tên.

**Solution:** Trace `rootSyncHistory.dataId` để xác định đúng FB account source.

## Related
- [Error Codes](error-codes.md)
- [Facebook Graph API](facebook-graph-api.md)
- [Insights API Queries](insights-queries.md)
- [Account ID Format](account-id-format.md)
