#!/usr/bin/env python3
"""
Import Facebook Marketing API documentation vào Nemi-AI.
Chạy script này sau khi đã start Nemi-AI server.

Usage:
    python scripts/import_fb_docs.py

Hoặc import từ code:
    from scripts.import_fb_docs import FB_API_DOCS_URLS, FB_GITHUB_REPOS
"""

import asyncio
import json
import os
import sys

# Thêm project root vào path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Facebook Marketing API Documentation URLs ───────────────────────────────

FB_API_DOCS_URLS = [
    # Facebook Graph API chính thức
    "https://developers.facebook.com/docs/marketing-apis/",
    "https://developers.facebook.com/docs/graph-api/",
    "https://developers.facebook.com/docs/graph-api/overview",
    "https://developers.facebook.com/docs/graph-api/using-graph-api/",
    "https://developers.facebook.com/docs/graph-api/reference/",
    "https://developers.facebook.com/docs/graph-api/reference/ad-account/",
    "https://developers.facebook.com/docs/graph-api/reference/campaign/",
    "https://developers.facebook.com/docs/graph-api/reference/ad-set/",
    "https://developers.facebook.com/docs/graph-api/reference/ad/",

    # Insights API
    "https://developers.facebook.com/docs/marketing-api/insights/",
    "https://developers.facebook.com/docs/marketing-api/insights/parameters/",
    "https://developers.facebook.com/docs/marketing-api/reference/ad-campaign-group/insights/",
    "https://developers.facebook.com/docs/marketing-api/reference/ad-account/insights/",

    # Error handling
    "https://developers.facebook.com/docs/graph-api/error-handling/",
    "https://developers.facebook.com/docs/marketing-api/error-reference/",
    "https://developers.facebook.com/docs/marketing-api/error-codes/",

    # Rate limiting
    "https://developers.facebook.com/docs/graph-api/overview/rate-limiting/",
    "https://developers.facebook.com/docs/marketing-api/rate-limiting/",

    # Authentication
    "https://developers.facebook.com/docs/facebook-login/guides/access-tokens/",
    "https://developers.facebook.com/docs/marketing-api/access/",

    # Pages & Business
    "https://developers.facebook.com/docs/pages/",
    "https://developers.facebook.com/docs/business-manager/",
    "https://developers.facebook.com/docs/marketing-api/businessmanager/",

    # Best practices
    "https://developers.facebook.com/docs/marketing-api/best-practices/",
    "https://developers.facebook.com/docs/graph-api/best-practices/",
    "https://developers.facebook.com/docs/marketing-api/guides/batch/",
]

FB_GITHUB_REPOS = [
    {
        "owner": "facebook",
        "name": "facebook-ads-python",
        "branch": "main",
        "path": "examples",
    },
    {
        "owner": "facebook",
        "name": "facebook-ads-python",
        "branch": "main",
        "path": "docs",
    },
    {
        "owner": "facebook",
        "name": "facebook-python-business-sdk",
        "branch": "main",
        "path": "examples",
    },
    {
        "owner": "facebook",
        "name": "facebook-python-business-sdk",
        "branch": "main",
        "path": "docs",
    },
    {
        "owner": "hieunm14",
        "name": "nemi-ai-fb-marketing-api",
        "branch": "main",
        "path": "docs/fb-marketing-api",
    },
]


async def import_urls():
    """Import FB API docs từ URLs qua HTTP request trực tiếp đến Nemi-AI API."""
    import aiohttp

    api_base = os.environ.get("NEMI_API_URL", "http://localhost:8000")

    # Config: dùng HTML reader để import
    config = {
        "reader": "HTML",
        "reader_config": {
            "URLs": {"values": FB_API_DOCS_URLS},
            "Convert To Markdown": {"value": True},
            "Recursive": {"value": False},
            "Max Depth": {"value": 2},
        },
        "chunker": "Recursive",
        "embedder": "OpenAI",
        "generator": "OpenAI",
    }

    print(f"📥 Importing {len(FB_API_DOCS_URLS)} URLs...")
    print(f"🔗 API: {api_base}")

    async with aiohttp.ClientSession() as session:
        # Gọi API import
        async with session.post(
            f"{api_base}/api/import",
            json={
                "file_config": {
                    "config": config,
                    "files": [],
                    "urls": FB_API_DOCS_URLS,
                }
            },
        ) as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"✅ Import thành công: {result}")
            else:
                text = await resp.text()
                print(f"❌ Import thất bại: {resp.status} - {text}")


def print_urls():
    """In danh sách URLs để copy-paste vào Nemi-AI UI."""
    print("=" * 70)
    print("📋 Facebook Marketing API Documentation URLs")
    print("=" * 70)
    print()
    print("=== HTML Reader - Copy các URLs này ===")
    print()
    for url in FB_API_DOCS_URLS:
        print(f"  {url}")
    print()
    print("=== Git Reader - Copy các repos này ===")
    print()
    for repo in FB_GITHUB_REPOS:
        print(f"  {repo['owner']}/{repo['name']} ({repo['branch']}/{repo['path']})")
    print()
    print("=" * 70)
    print("💡 Dùng HTML Reader trong Nemi-AI UI để import từ URLs")
    print("   hoặc Git Reader để import từ GitHub repos")
    print("=" * 70)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Import Facebook Marketing API docs vào Nemi-AI"
    )
    parser.add_argument(
        "--urls-only",
        action="store_true",
        help="Chỉ in danh sách URLs, không import",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("NEMI_API_URL", "http://localhost:8000"),
        help="Nemi-AI API URL (default: http://localhost:8000)",
    )

    args = parser.parse_args()

    if args.urls_only:
        print_urls()
    else:
        os.environ["NEMI_API_URL"] = args.api_url
        asyncio.run(import_urls())
