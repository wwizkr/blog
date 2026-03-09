from __future__ import annotations

import re
from html import unescape
from urllib.parse import parse_qs, quote_plus, unquote, urlparse, urlunparse

from bs4 import BeautifulSoup

from collector.base import BaseCollector


class GoogleSerpCollector(BaseCollector):
    channel_code = "google_serp"
    display_name = "구글 SERP(블로그/커뮤니티)"

    _allowed_exact_hosts = {
        "blog.naver.com",
        "m.blog.naver.com",
        "cafe.naver.com",
        "m.cafe.naver.com",
        "brunch.co.kr",
        "velog.io",
        "medium.com",
        "post.naver.com",
        "blog.daum.net",
        "m.blog.daum.net",
        "clien.net",
        "theqoo.net",
        "instiz.net",
        "ppomppu.co.kr",
        "ruliweb.com",
        "inven.co.kr",
        "etoland.co.kr",
        "todayhumor.co.kr",
        "dogdrip.net",
        "bbs.ruliweb.com",
        "m.dcinside.com",
        "gall.dcinside.com",
    }
    _allowed_suffix_hosts = {
        ".tistory.com",
        ".medium.com",
        ".velog.io",
        ".brunch.co.kr",
        ".clien.net",
        ".ppomppu.co.kr",
        ".inven.co.kr",
        ".ruliweb.com",
        ".etoland.co.kr",
        ".todayhumor.co.kr",
        ".dogdrip.net",
        ".dcinside.com",
    }
    _exclude_host_tokens = {
        "google.com",
        "google.co.kr",
        "youtube.com",
        "youtu.be",
        "wikipedia.org",
        "namu.wiki",
        "shopping.naver.com",
    }
    _exclude_path_tokens = (
        "/search",
        "/tag",
        "/category",
        "/rss",
        "/login",
        "/signin",
        "/signup",
        "/join",
    )
    _drop_query_keys = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "recommendcode",
        "recommendtrackingcode",
    }

    def collect(self, keyword: str, limit: int = 5) -> list[dict]:
        candidate_limit = max(10, limit * 4)
        search_url = (
            f"https://www.google.com/search?hl=ko&gl=kr&num={candidate_limit}"
            f"&q={quote_plus(keyword)}"
        )
        html = self._fetch_html(search_url, timeout=15)
        if not html:
            return []

        candidates = self._extract_result_urls(html, limit=candidate_limit)
        if not candidates:
            return []

        rows: list[dict] = []
        seen_urls: set[str] = set()
        for url in candidates:
            if len(rows) >= limit:
                break
            normalized_url = self._normalize_content_url(url)
            if not normalized_url or normalized_url in seen_urls:
                continue

            detail_html = self._fetch_html(normalized_url, timeout=15)
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
                    "article",
                    ".entry-content",
                    ".tt_article_useless_p_margin",
                    ".se-main-container",
                    ".article_view",
                    ".article-content",
                    ".post-content",
                    ".board_view",
                    "#article-view",
                    ".view_content",
                    ".content",
                    "#content",
                    ".xe_content",
                    ".rd_body",
                    ".memo_content",
                ],
                drop_selectors=[
                    "header",
                    "footer",
                    "nav",
                    "aside",
                    ".adsbygoogle",
                    "ins.adsbygoogle",
                    ".kakao_ad_area",
                    ".revenue_unit_wrap",
                    ".another_category",
                    ".related-articles",
                    ".comment",
                    ".comments",
                ],
            )
            if len(payload["body_text"]) < 80:
                continue
            if not self._is_relevant_content(keyword=keyword, title=title, body_text=payload["body_text"]):
                continue

            seen_urls.add(normalized_url)
            rows.append(
                {
                    "title": title[:500],
                    "body_text": payload["body_text"],
                    "body_html": payload["body_html"],
                    "source_url": normalized_url,
                    "author": self._derive_author(normalized_url),
                    "images": payload["images"],
                }
            )

        return rows

    def _extract_result_urls(self, html: str, limit: int) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        found: list[str] = []
        for anchor in soup.select("a[href]"):
            href = self._unwrap_google_result_url((anchor.get("href") or "").strip())
            if not self._is_allowed_result_url(href):
                continue
            if href in found:
                continue
            found.append(href)
            if len(found) >= limit:
                break

        if found:
            return found

        raw_urls = re.findall(r"/url\?q=([^&\"'>]+)", html)
        for raw in raw_urls:
            href = self._unwrap_google_result_url(f"/url?q={raw}")
            if not self._is_allowed_result_url(href):
                continue
            if href in found:
                continue
            found.append(href)
            if len(found) >= limit:
                break
        return found

    def _unwrap_google_result_url(self, href: str) -> str:
        if not href:
            return ""
        url = unescape(href.strip())
        if url.startswith("/url?"):
            url = f"https://www.google.com{url}"
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if "google." in host:
            q = parse_qs(parsed.query or "")
            target = (q.get("q") or [None])[0]
            if target:
                decoded = unquote(unescape(target)).strip()
                if decoded.startswith("//"):
                    decoded = f"https:{decoded}"
                return decoded
        return url

    def _normalize_content_url(self, url: str) -> str:
        if not url:
            return ""
        try:
            parsed = urlparse(url)
            query = parse_qs(parsed.query or "", keep_blank_values=False)
            filtered = []
            for key, values in query.items():
                if key.lower() in self._drop_query_keys:
                    continue
                for value in values:
                    filtered.append((key, value))
            filtered.sort()
            return urlunparse(parsed._replace(query="&".join([f"{k}={quote_plus(v)}" for k, v in filtered]), fragment=""))
        except Exception:
            return url.split("#", 1)[0].strip()

    def _normalize_match_text(self, value: str) -> str:
        text = str(value or "").casefold()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^0-9a-z가-힣 ]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _is_relevant_content(self, keyword: str, title: str, body_text: str) -> bool:
        keyword_norm = self._normalize_match_text(keyword)
        title_norm = self._normalize_match_text(title)
        body_norm = self._normalize_match_text(body_text[:4000])
        haystack = f"{title_norm} {body_norm}".strip()
        if not keyword_norm or not haystack:
            return False
        compact_keyword = keyword_norm.replace(" ", "")
        compact_haystack = haystack.replace(" ", "")
        if compact_keyword and compact_keyword in compact_haystack:
            return True
        tokens = [token for token in keyword_norm.split(" ") if len(token) >= 2]
        if not tokens:
            return False
        matched = sum(1 for token in dict.fromkeys(tokens) if token in haystack)
        required = 1 if len(tokens) == 1 else 2
        return matched >= required

    def _is_allowed_result_url(self, url: str) -> bool:
        if not url or not url.startswith("http"):
            return False
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if not host:
            return False
        if any(token == host or host.endswith(f".{token}") for token in self._exclude_host_tokens):
            return False
        if not self._is_allowed_host(host):
            return False

        path = (parsed.path or "").lower()
        if any(token in path for token in self._exclude_path_tokens):
            return False
        return self._looks_like_article_url(host, path)

    def _is_allowed_host(self, host: str) -> bool:
        if host in self._allowed_exact_hosts:
            return True
        if any(host.endswith(suffix) for suffix in self._allowed_suffix_hosts):
            return True
        return any(token in host for token in ["blog", "cafe", "forum", "community", "bbs"])

    def _looks_like_article_url(self, host: str, path: str) -> bool:
        if re.search(r"/\d{3,}(?:/)?$", path):
            return True
        if any(token in path for token in ["/entry/", "/archives/", "/articles/", "/board/", "/view/"]):
            return True
        if "dcinside.com" in host and "/board/" in path:
            return True
        if "clien.net" in host and "/service/" in path:
            return True
        if "ruliweb.com" in host and "/best/" in path:
            return True
        return len([part for part in path.split("/") if part]) >= 2

    def _derive_author(self, url: str) -> str:
        host = (urlparse(url).netloc or "").lower()
        return host or "unknown"
