from __future__ import annotations

import re
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup

from collector.base import BaseCollector


class TistoryCollector(BaseCollector):
    channel_code = "tistory"
    display_name = "티스토리"

    def collect(self, keyword: str, limit: int = 5) -> list[dict]:
        search_url = f"https://search.daum.net/search?w=blog&q={quote_plus(keyword)}"
        html = self._fetch_html(search_url)

        candidates: list[str] = []
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for anchor in soup.select("a[href]"):
                href = (anchor.get("href") or "").strip()
                if self._is_valid_tistory_url(href) and href not in candidates:
                    candidates.append(href)
                if len(candidates) >= limit * 4:
                    break

        if not candidates:
            candidates = self._search_links_by_domain(keyword=keyword, domain="tistory.com", limit=limit * 4)
        if not candidates:
            return []

        rows: list[dict] = []
        for url in candidates:
            if len(rows) >= limit:
                break
            detail_html = self._fetch_html(url)
            if not detail_html:
                continue
            detail_soup = BeautifulSoup(detail_html, "html.parser")
            meta_title = detail_soup.select_one("meta[property='og:title']")
            title = (meta_title.get("content").strip() if meta_title and meta_title.get("content") else None) or (
                detail_soup.title.get_text(strip=True) if detail_soup.title else f"{keyword} 글"
            )

            payload = self._extract_content_payload(
                detail_html,
                url,
                content_selectors=[
                    ".entry-content",
                    ".tt_article_useless_p_margin",
                    ".article-content",
                    "#article-view",
                    ".post-content",
                    ".contents_style",
                    ".area_view",
                    "article",
                ],
                drop_selectors=[
                    "ins.adsbygoogle",
                    ".revenue_unit_wrap",
                    ".kakao_ad_area",
                    ".another_category",
                    ".related-articles",
                    ".widget",
                    "aside",
                ],
            )
            if len(payload["body_text"]) < 40:
                continue
            rows.append(
                {
                    "title": title[:500],
                    "body_text": payload["body_text"],
                    "body_html": payload["body_html"],
                    "source_url": url,
                    "author": "unknown",
                    "images": payload["images"],
                }
            )

        return rows

    def _is_valid_tistory_url(self, url: str) -> bool:
        if not url or not url.startswith("http"):
            return False
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if host != "tistory.com" and not host.endswith(".tistory.com"):
            return False
        path = (parsed.path or "").lower()
        exclude_patterns = ["/search", "/tag", "/category", "daumsearch", "/m/", "/rss"]
        if any(p in url.lower() for p in exclude_patterns):
            return False
        if re.search(r"/\d+$", path):
            return True
        if "/entry/" in path:
            return True
        return False

