# Nemi-AI

> Facebook Marketing API RAG Assistant — tra cứu tài liệu Facebook Marketing API, lỗi và cách xử lý bằng RAG.

Nemi-AI là ứng dụng RAG (Retrieval-Augmented Generation) mã nguồn mở, được xây dựng trên nền tảng **Weaviate** vector database, cho phép bạn nhập tài liệu Facebook Marketing API, tra cứu mã lỗi, best practices và các vấn đề thường gặp bằng ngôn ngữ tự nhiên.

## Tính năng

- **Tìm kiếm thông minh**: Hỏi đáp bằng ngôn ngữ tự nhiên về Facebook Marketing API
- **RAG Pipeline**: Hybrid search + Window retrieval cho kết quả chính xác
- **Đa dạng LLM**: Hỗ trợ OpenAI, Anthropic Claude, Ollama (local), Groq, Cohere, v.v.
- **Nhập liệu linh hoạt**: Tài liệu PDF, HTML, Markdown, GitHub, web crawl
- **Chunking thông minh**: Token, Sentence, Semantic, Recursive, Code chunker
- **Chạy local hoặc cloud**: Dùng Ollama + HuggingFace local, hoặc LLM cloud

## Kiến trúc

```
┌──────────────┐     ┌─────────────┐     ┌──────────┐
│  Next.js UI  │────▶│ FastAPI API │────▶│ Weaviate │
│  (React/TS)  │     │  (Python)   │     │  Vector  │
│              │◀────│             │◀────│   DB     │
└──────────────┘     └──────┬──────┘     └──────────┘
                            │
                    ┌───────┴───────┐
                    │   LLM/Embed   │
                    │  (OpenAI,     │
                    │  Ollama, ...) │
                    └───────────────┘
```

## Quickstart

### Yêu cầu
- Python >= 3.10, < 3.13
- Weaviate instance (local hoặc cloud)
- (Optional) Docker

### Cài đặt

```bash
# Clone repo
git clone https://github.com/hieunm14/nemi-ai-fb-marketing-api
cd nemi-ai-fb-marketing-api

# (Recommended) Tạo virtual environment
python -m venv venv
source venv/bin/activate

# Cài đặt package
pip install -e .
```

### Cấu hình

Copy và điền API keys:

```bash
cp nemi_ai/.env.example .env
```

Biến môi trường quan trọng:

| Variable | Mô tả |
|----------|-------|
| `WEAVIATE_URL_NEMI` | URL Weaviate instance (vd: `http://localhost:8177`) |
| `WEAVIATE_API_KEY_NEMI` | API Key Weaviate (nếu có auth) |
| `OPENAI_API_KEY` | API Key cho Generation (OpenAI / DeepSeek / OpenAI-compatible) |
| `OPENAI_BASE_URL` | Base URL cho Generation (mặc định: `https://api.openai.com/v1`) |
| `OPENAI_MODEL` | Model name (mặc định: tự động fetch từ API) |
| `OLLAMA_URL` | URL Ollama local (mặc định: `http://localhost:11434`) |

### Chạy

```bash
# Start Nemi-AI
nemi start
```

Truy cập `http://localhost:8000` để mở UI.

### Hoặc dùng Docker

```bash
docker-compose up
```

## Facebook Marketing API Knowledge Base

Nemi-AI được thiết kế để tra cứu các tài liệu và vấn đề Facebook Marketing API:

### Error Codes

| Code | Ý nghĩa | Xử lý |
|------|---------|-------|
| **1** | General error / bad request | Halve `limit` và retry |
| **2** | Temporary server error | Retry up to 8 lần |
| **960** | Timeout / too slow | Retry (giống code 2) |
| **80004** | Rate limited | Cooldown 60 phút |
| **400/403** | Token expired/disconnected | Fail, ghi vào SyncHistory |

### Insights API

**✅ Đúng — dùng `date_preset`:**
```bash
/act_12345/insights?date_preset=last_3d&time_increment=1
```

**✅ Đúng — single day với `time_range`:**
```bash
/act_12345/insights?time_range={"since":"2026-06-06","until":"2026-06-06"}
```

**❌ Sai — `since/until` không có `time_range` trả về lifetime total:**
```bash
# KHÔNG dùng cách này
/act_12345/insights?since=2026-06-01&until=2026-06-07
```

### Account ID Format

- `account_id` trong `fb_campaign`, `fb_adset`, `fb_ad`: **raw numeric ID** (vd: `997347632562145`)
- `act_` prefix chỉ xuất hiện trong `fb_ad_account.id` và API requests
- Khi JOIN từ campaign/adset/ad, **không** dùng `act_` prefix

## Import tài liệu FB API

Sau khi start Nemi-AI, vào tab **Ingestion** để import:
- **HTML Reader**: Import từ Facebook Developer docs URLs
- **Git Reader**: Import từ GitHub repos về FB API
- **Firecrawl**: Crawl toàn bộ FB API documentation site
- **Basic Reader**: Import PDF files (FB API specs, guides)

## Cấu hình Generation (LLM)

Mặc định Nemi-AI dùng OpenAI Generator. Bạn có thể đổi model và base URL để xài DeepSeek hoặc bất kỳ OpenAI-compatible API nào.

### Dùng DeepSeek (cách nhanh)

Set trong file `.env`:

```bash
# Generation dùng DeepSeek
OPENAI_API_KEY=sk-deepseek-xxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat

# Embedding vẫn dùng OpenAI (DeepSeek không có embedding)
OPENAI_API_KEY=sk-openai-xxx   # hoặc dùng Ollama embedding local
```

**Hoặc set qua UI:** Settings → Generation → OpenAI → sửa URL thành `https://api.deepseek.com/v1`, nhập DeepSeek API key và chọn model.

> **Lưu ý:** DeepSeek API chỉ hỗ trợ generation (chat), **không hỗ trợ embedding**. Bạn cần dùng OpenAI hoặc Ollama riêng cho embedding (config trong tab Embedding).

### Dùng hoàn toàn local (Ollama)

```bash
# Cả generation + embedding đều local
OLLAMA_URL=http://localhost:11434
OPENAI_API_KEY=  # không cần
```

## Phát triển

```bash
# Frontend
cd frontend
npm install
npm run dev

# Backend (terminal riêng)
pip install -e ".[dev]"
nemi start --port 8000 --host 0.0.0.0
```

## License

BSD License. Xem [LICENSE](LICENSE).
