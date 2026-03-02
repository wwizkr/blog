from __future__ import annotations

import re
from html import unescape
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from bs4 import BeautifulSoup

from collector.base import BaseCollector


class NaverBlogCollector(BaseCollector):
    channel_code = "naver_blog"
    display_name = "네이버 블로그"

    def collect(self, keyword: str, limit: int = 5) -> list[dict]:
        search_url = f"https://search.naver.com/search.naver?where=blog&query={quote_plus(keyword)}"
        html = self._fetch_html(search_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        candidates: list[str] = []
        for anchor in soup.select("a[href]"):
            for href in self._extract_anchor_urls(anchor):
                if self._is_valid_blog_url(href) and href not in candidates:
                    candidates.append(href)
            if len(candidates) >= limit * 4:
                break

        if not candidates:
            for href in self._extract_blog_urls_from_html(html):
                if self._is_valid_blog_url(href) and href not in candidates:
                    candidates.append(href)
                if len(candidates) >= limit * 4:
                    break

        if not candidates:
            candidates = self._search_links_by_domain(keyword=keyword, domain="blog.naver.com", limit=limit * 4)
        if not candidates:
            return []

        rows: list[dict] = []
        for url in candidates:
            if len(rows) >= limit:
                break

            mobile_url = self._to_mobile_url(url)
            detail_html = self._fetch_html(mobile_url) or self._fetch_html(url)
            if not detail_html:
                continue

            detail_soup = BeautifulSoup(detail_html, "html.parser")
            meta_title = detail_soup.select_one("meta[property='og:title']")
            title = (meta_title.get("content").strip() if meta_title and meta_title.get("content") else None) or (
                detail_soup.title.get_text(strip=True) if detail_soup.title else f"{keyword} 포스트"
            )

            payload = self._extract_content_payload(
                detail_html,
                mobile_url,
                content_selectors=[
                    ".se-main-container",
                    "#postViewArea",
                    ".se_component_wrap",
                    ".post-view",
                    "#viewTypeSelector",
                    "article",
                ],
                drop_selectors=[
                    ".se-sticker-image",
                    ".se-module-oglink",
                    ".se-map",
                    ".__se_module_data",
                    "ins.adsbygoogle",
                    ".kakao_ad_area",
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

    def _is_valid_blog_url(self, url: str) -> bool:
        if not url or not url.startswith("http"):
            return False
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if host != "blog.naver.com" and host != "m.blog.naver.com":
            return False

        path = (parsed.path or "").strip("/")
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[-1].isdigit():
            return True

        query = parse_qs(parsed.query or "")
        if query.get("logNo"):
            return True

        if re.search(r"/\d{6,}$", parsed.path or ""):
            return True
        return False

    def _extract_anchor_urls(self, anchor) -> list[str]:
        out: list[str] = []
        for attr in ["href", "data-url", "data-href"]:
            raw = (anchor.get(attr) or "").strip()
            if not raw:
                continue
            resolved = self._unwrap_result_url(raw)
            if resolved and resolved not in out:
                out.append(resolved)
        return out

    def _unwrap_result_url(self, raw_url: str) -> str:
        if not raw_url:
            return ""

        url = raw_url.strip()
        if url.startswith("//"):
            url = f"https:{url}"
        url = unescape(url)

        parsed = urlparse(url)
        if not parsed.scheme and url.startswith("/"):
            url = f"https://search.naver.com{url}"
            parsed = urlparse(url)

        host = (parsed.netloc or "").lower()
        if "search.naver.com" in host:
            q = parse_qs(parsed.query or "")
            for key in ["url", "u", "target", "rurl"]:
                candidate = (q.get(key) or [None])[0]
                if not candidate:
                    continue
                decoded = unquote(unescape(candidate)).strip()
                if decoded.startswith("//"):
                    decoded = f"https:{decoded}"
                if decoded.startswith("http"):
                    return decoded

        return url

    def _extract_blog_urls_from_html(self, html: str) -> list[str]:
        found: list[str] = []
        if not html:
            return found

        direct = re.findall(r"https?://(?:m\.)?blog\.naver\.com/[^\s\"'<>]+", html)
        escaped = re.findall(r"https?:\\\\/\\\\/(?:m\\.)?blog\\.naver\\.com\\\\/[^\s\"'<>]+", html)
        for item in direct + escaped:
            url = item.replace("\\/", "/")
            url = unescape(url)
            if url not in found:
                found.append(url)
        return found

    def _to_mobile_url(self, url: str) -> str:
        parsed = urlparse(url)
        if "m.blog.naver.com" in (parsed.netloc or ""):
            return url

        query = parse_qs(parsed.query or "")
        blog_id = (query.get("blogId") or [None])[0]
        log_no = (query.get("logNo") or [None])[0]
        if blog_id and log_no:
            return f"https://m.blog.naver.com/{blog_id}/{log_no}"

        path = (parsed.path or "").strip("/")
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[-1].isdigit():
            return f"https://m.blog.naver.com/{parts[-2]}/{parts[-1]}"

        return url

