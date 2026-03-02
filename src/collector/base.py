from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from html import unescape
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag


class BaseCollector(ABC):
    channel_code: str
    display_name: str
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    @abstractmethod
    def collect(self, keyword: str, limit: int = 5) -> list[dict]:
        """
        Returns:
            [{"title": str, "body_text": str, "body_html": str|None, "source_url": str, "author": str, "images": list[str]}, ...]
        """
        raise NotImplementedError

    def get_channel_info(self) -> tuple[str, str]:
        return self.channel_code, self.display_name

    def _fetch_html(self, url: str, timeout: int = 12) -> str | None:
        try:
            response = requests.get(url, timeout=timeout, headers={"User-Agent": self.user_agent})
            response.raise_for_status()
            return response.text
        except Exception:
            return None

    def _is_domain_url(self, href: str, domain: str) -> bool:
        try:
            parsed = urlparse(href)
        except Exception:
            return False
        if parsed.scheme not in {"http", "https"}:
            return False
        host = (parsed.netloc or "").lower()
        root = domain.lower()
        return host == root or host.endswith(f".{root}")

    def _search_links_by_domain(self, keyword: str, domain: str, limit: int = 10) -> list[str]:
        query = f"site:{domain} {keyword}"
        search_url = f"https://duckduckgo.com/html/?q={requests.utils.quote(query)}"
        html = self._fetch_html(search_url, timeout=15)

        found: list[str] = []
        if html:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.select("a[href]"):
                href = self._normalize_result_url((a.get("href") or "").strip())
                if self._is_domain_url(href, domain) and href not in found:
                    found.append(href)
                if len(found) >= limit:
                    break

        if len(found) >= limit:
            return found[:limit]

        for href in self._search_links_by_bing_rss(keyword=keyword, domain=domain, limit=limit):
            if href not in found:
                found.append(href)
            if len(found) >= limit:
                break

        return found[:limit]

    def _search_links_by_bing_rss(self, keyword: str, domain: str, limit: int = 10) -> list[str]:
        query = requests.utils.quote(f"site:{domain} {keyword}")
        rss_url = f"https://www.bing.com/search?q={query}&format=rss"
        xml = self._fetch_html(rss_url, timeout=15)
        if not xml:
            return []

        links = [m.strip() for m in re.findall(r"<link>(https?://[^<]+)</link>", xml)]
        found: list[str] = []
        for href in links:
            href = self._normalize_result_url(href)
            if not self._is_domain_url(href, domain):
                continue
            if href in found:
                continue
            found.append(href)
            if len(found) >= limit:
                break
        return found

    def _normalize_result_url(self, href: str) -> str:
        if not href:
            return ""
        if href.startswith("//"):
            href = f"https:{href}"
        if "duckduckgo.com/l/?" in href:
            try:
                parsed = urlparse(href)
                q = parse_qs(parsed.query)
                uddg = (q.get("uddg") or [None])[0]
                if uddg:
                    href = unquote(uddg)
            except Exception:
                pass
        return href

    def _extract_text_and_images(self, html: str, base_url: str) -> tuple[str, list[str]]:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        body = soup.body or soup
        text = " ".join(body.get_text(" ", strip=True).split())
        if len(text) > 20000:
            text = text[:20000]

        image_urls = self._extract_images_from_element(body, base_url)
        return text, image_urls

    def _extract_content_payload(
        self,
        html: str,
        base_url: str,
        content_selectors: list[str] | None = None,
        drop_selectors: list[str] | None = None,
    ) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        content_tag: Tag | None = None
        for selector in content_selectors or []:
            found = soup.select_one(selector)
            if found:
                content_tag = found
                break

        if content_tag is None:
            content_tag = soup.body or soup

        for selector in drop_selectors or []:
            for node in content_tag.select(selector):
                node.decompose()

        body_html = str(content_tag)
        body_text = " ".join(content_tag.get_text(" ", strip=True).split())
        body_text = re.sub(r"\s+", " ", body_text).strip()
        if len(body_text) > 20000:
            body_text = body_text[:20000]

        images = self._extract_images_from_element(content_tag, base_url)
        return {
            "body_text": body_text,
            "body_html": body_html,
            "images": images,
        }

    def _extract_images_from_element(self, element: Tag, base_url: str) -> list[str]:
        image_urls: list[str] = []
        for img in element.select("img"):
            if self._should_skip_image_tag(img):
                continue

            candidates = self._collect_image_candidates(img)
            if not candidates:
                continue

            best = sorted(candidates, key=self._image_candidate_score, reverse=True)[0]
            full = self._normalize_image_url(urljoin(base_url, best))
            if not full or full in image_urls:
                continue

            image_urls.append(full)
            if len(image_urls) >= 20:
                break
        return image_urls

    def _should_skip_image_tag(self, img: Tag) -> bool:
        cls = " ".join(img.get("class") or []).lower()
        if any(token in cls for token in ["sticker", "emoji", "profile", "avatar", "badge"]):
            return True

        src = ((img.get("src") or "") + " " + (img.get("data-src") or "") + " " + (img.get("data-lazy-src") or "")).lower()
        if any(token in src for token in ["/original_4.gif", "spacer", "blank.gif", "emoji", "sticker", "storep-phinf.pstatic.net/pick_manager", "type=p100_100"]):
            return True

        return False

    def _collect_image_candidates(self, img: Tag) -> list[str]:
        candidates: list[str] = []

        def _push(value: str | None) -> None:
            v = (value or "").strip()
            if not v or v.startswith("data:"):
                return
            if v.startswith("//"):
                v = f"https:{v}"
            if v not in candidates:
                candidates.append(v)

        for attr in [
            "data-original",
            "data-origin-src",
            "data-src",
            "data-lazy-src",
            "data-url",
            "data-image",
            "data-file",
            "src",
        ]:
            _push(img.get(attr))

        for value in self._collect_linkdata_candidates(img):
            _push(value)

        _push(self._pick_best_from_srcset(img.get("data-srcset") or ""))
        _push(self._pick_best_from_srcset(img.get("srcset") or ""))
        return candidates

    def _collect_linkdata_candidates(self, img: Tag) -> list[str]:
        out: list[str] = []

        parent = img
        for _ in range(5):
            parent = parent.parent if parent else None
            if parent is None:
                break
            raw = parent.get("data-linkdata")
            if not raw:
                continue

            try:
                data = json.loads(unescape(str(raw)))
            except Exception:
                continue

            src = str(data.get("src") or "").strip()
            if src:
                out.append(src)

            try:
                original_width = int(str(data.get("originalWidth") or "0"))
            except Exception:
                original_width = 0

            if src and original_width >= 960:
                out.append(self._set_image_type_param(src, f"w{original_width}"))

            break

        return out

    def _set_image_type_param(self, url: str, type_value: str) -> str:
        try:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
            query["type"] = [type_value]
            new_query = urlencode(query, doseq=True)
            return urlunparse(parsed._replace(query=new_query))
        except Exception:
            if "?" in url:
                return f"{url}&type={type_value}"
            return f"{url}?type={type_value}"

    def _pick_best_from_srcset(self, srcset: str) -> str:
        if not srcset:
            return ""

        best_url = ""
        best_score = -1
        for chunk in srcset.split(","):
            item = chunk.strip()
            if not item:
                continue
            parts = item.split()
            url = parts[0].strip()
            descriptor = parts[1].strip().lower() if len(parts) > 1 else ""
            score = 1
            m_w = re.match(r"^(\d+)w$", descriptor)
            m_x = re.match(r"^(\d+(?:\.\d+)?)x$", descriptor)
            if m_w:
                score = int(m_w.group(1))
            elif m_x:
                score = int(float(m_x.group(1)) * 1000)

            if score > best_score:
                best_score = score
                best_url = url

        return best_url

    def _image_candidate_score(self, url: str) -> tuple[int, int]:
        lowered = (url or "").lower()
        thumb_penalty = 1 if self._is_thumbnail_like(lowered) else 0
        return (-thumb_penalty, len(url or ""))

    def _is_thumbnail_like(self, lowered_url: str) -> bool:
        thumb_tokens = [
            "thumbnail",
            "small",
            "icon",
            "preview",
            "/c80x",
            "/c160x",
            "/c240x",
            "/c320x",
            "/w80",
            "/w120",
            "/w160",
            "/s72-c",
            "w80_blur",
            "storep-phinf.pstatic.net/pick_manager",
            "type=p100_100",
        ]
        if any(token in lowered_url for token in thumb_tokens):
            return True

        for m in re.finditer(r"[?&](w|width|h|height)=(\d+)(?:[&#]|$)", lowered_url):
            try:
                val = int(m.group(2))
            except Exception:
                continue
            if val <= 320:
                return True

        m_type = re.search(r"[?&]type=(w(\d+)|s(\d+)|small|thumb)(?:[&#]|$)", lowered_url)
        if m_type:
            if m_type.group(2):
                return int(m_type.group(2)) <= 320
            if m_type.group(3):
                return int(m_type.group(3)) <= 3
            return True

        return False

    def _normalize_image_url(self, url: str) -> str:
        if not url:
            return ""

        try:
            parsed = urlparse(url)
            query = parse_qs(parsed.query)
        except Exception:
            return url

        parsed_host = (parsed.netloc or "").lower()
        if parsed_host == "mblogthumb-phinf.pstatic.net":
            return urlunparse(parsed._replace(query="type=w966"))

        if not query:
            return url

        changed = False
        normalized: dict[str, list[str]] = {}
        for key, values in query.items():
            k = key.lower()
            if k in {"w", "width", "h", "height", "resize", "size", "thumbnail", "thumb"}:
                changed = True
                continue

            if k == "type":
                v0 = (values[0] if values else "").lower()
                m_w = re.match(r"^w(\d+)$", v0)
                m_s = re.match(r"^s(\d+)$", v0)
                if m_w and int(m_w.group(1)) <= 320:
                    changed = True
                    continue
                if m_s and int(m_s.group(1)) <= 3:
                    changed = True
                    continue
                if v0 in {"small", "thumb"}:
                    changed = True
                    continue

            normalized[key] = values

        if not changed:
            return url

        new_query = urlencode(normalized, doseq=True)
        return urlunparse(parsed._replace(query=new_query))




