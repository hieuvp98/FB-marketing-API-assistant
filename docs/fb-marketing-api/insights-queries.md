# Facebook Insights API Query Patterns

## ⚠️ QUAN TRỌNG: Date Parameters

### ✅ ĐÚNG — Dùng `date_preset` (khuyên dùng)

```bash
# 3 ngày gần nhất, daily breakdown
GET /act_12345/insights?date_preset=last_3d&time_increment=1

# Hôm qua
GET /act_12345/insights?date_preset=yesterday

# 7 ngày qua
GET /act_12345/insights?date_preset=last_7d

# Tháng này
GET /act_12345/insights?date_preset=this_month

# 30 ngày qua
GET /act_12345/insights?date_preset=last_30d
```

### ✅ ĐÚNG — Dùng `time_range` cho 1 ngày cụ thể

```bash
# Lấy data đúng 1 ngày 2026-06-06
GET /act_12345/insights?time_range={"since":"2026-06-06","until":"2026-06-06"}
```

### ❌ SAI — `since/until` KHÔNG có `time_increment`

```bash
# SAi! Trả về LIFETIME TOTAL chứ không phải daily!
GET /act_12345/insights?since=2026-06-01&until=2026-06-07
```

Facebook Graph API v23.0+ **bỏ qua** `since`/`until` và trả về lifetime data khi không có `time_increment`.

## Time Increment

| time_increment | Kết quả |
|----------------|---------|
| `1` | Daily breakdown |
| `7` | Weekly breakdown |
| Không set | Tổng cho toàn bộ period |

## Common Fields

```bash
# Minimal (tránh timeout)
fields=spend,actions

# Đầy đủ
fields=spend,impressions,clicks,ctr,cpc,cpm,actions,reach,frequency
```

## Actions JSONB

Actions trả về dạng JSON array:

```json
{
  "actions": [
    {"action_type": "link_click", "value": "150"},
    {"action_type": "purchase", "value": "12"},
    {"action_type": "add_to_cart", "value": "45"}
  ]
}
```

Trong SQL, query actions bằng:

```sql
SELECT
  spend,
  actions::jsonb AS actions_raw,
  (SELECT value::numeric FROM jsonb_array_elements(actions::jsonb) 
   WHERE action_type = 'purchase') AS purchases
FROM fb_insights_ad_account;
```

## Best Practices

1. **Luôn dùng `date_preset`** thay vì `since/until`
2. **Dùng `time_range` JSON object** cho single-day query
3. **Minimal fields** cho prefetch (spend, actions)
4. **Max 12 ad accounts per batch** để tránh timeout

## Related
- [Facebook Graph API](facebook-graph-api.md)
- [Error Codes](error-codes.md)
- [Account ID Format](account-id-format.md)
