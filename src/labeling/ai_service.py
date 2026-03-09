from __future__ import annotations

import json
import os

import requests

from core.settings_keys import LabelSettingKeys
from storage.repositories import AIProviderRepository, AppSettingRepository


class LabelingAIService:
    def pick_provider(self, *, prefer_paid: bool) -> object | None:
        explicit_id = _configured_provider_id(prefer_paid=prefer_paid)
        if explicit_id:
            configured = AIProviderRepository.get_by_id(explicit_id)
            if self._is_provider_ready(configured, prefer_paid=prefer_paid):
                return configured

        rows = AIProviderRepository.list_all(enabled_only=True)
        for row in rows:
            if self._is_provider_ready(row, prefer_paid=prefer_paid):
                return row
        return None

    def _is_provider_ready(self, row: object | None, *, prefer_paid: bool) -> bool:
        if not row:
            return False
        if not bool(getattr(row, "is_enabled", False)):
            return False
        if bool(getattr(row, "is_paid", False)) != bool(prefer_paid):
            return False
        provider_name = str(getattr(row, "provider", "") or "").strip().lower()
        if provider_name not in {"openai", "google", "gemini"}:
            return False
        alias = str(getattr(row, "api_key_alias", "") or "").strip()
        if alias and not os.getenv(alias):
            return False
        return True

    def label_content(self, *, title: str, body: str, prefer_paid: bool) -> dict | None:
        provider = self.pick_provider(prefer_paid=prefer_paid)
        if not provider:
            return None
        payload = {
            "title": str(title or "")[:300],
            "body": str(body or "")[:8000],
        }
        if str(provider.provider).strip().lower() == "openai":
            return self._label_content_openai(provider, payload)
        return self._label_content_gemini(provider, payload)

    def label_image(self, *, image_url: str, prefer_paid: bool) -> dict | None:
        provider = self.pick_provider(prefer_paid=prefer_paid)
        if not provider:
            return None
        provider_name = str(provider.provider or "").strip().lower()
        if provider_name != "openai":
            return None
        return self._label_image_openai(provider, str(image_url or ""))

    def _label_content_openai(self, provider, payload: dict) -> dict | None:
        api_key = os.getenv(str(provider.api_key_alias or "").strip())
        if not api_key:
            return None
        body = {
            "model": provider.model_name,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return strict JSON only. "
                        "Fields: tone, sentiment, topics, structure_type, title_type, "
                        "commercial_intent, writing_fit_score, cta_present, faq_structure, quality_score, confidence. "
                        "tone in Korean short label. sentiment in Korean short label. topics must be JSON array. "
                        "Scores use integers 1-5 except confidence 0-1 float."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Analyze this Korean article for content labeling.\n"
                        f"Title: {payload['title']}\n\n"
                        f"Body:\n{payload['body']}"
                    ),
                },
            ],
        }
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=45,
        )
        response.raise_for_status()
        result = response.json()
        content = (((result.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        return self._safe_json_object(content)

    def _label_content_gemini(self, provider, payload: dict) -> dict | None:
        api_key = os.getenv(str(provider.api_key_alias or "").strip())
        if not api_key:
            return None
        prompt = (
            "Return JSON only with keys: tone, sentiment, topics, structure_type, title_type, "
            "commercial_intent, writing_fit_score, cta_present, faq_structure, quality_score, confidence.\n"
            "Use Korean short labels for tone/sentiment. topics must be array. integer scores 1-5, confidence 0-1.\n\n"
            f"Title: {payload['title']}\n\nBody:\n{payload['body']}"
        )
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{provider.model_name}:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=45,
        )
        response.raise_for_status()
        result = response.json()
        candidates = result.get("candidates") or []
        parts = (((candidates[0] if candidates else {}).get("content") or {}).get("parts") or [])
        text = "".join(str(part.get("text") or "") for part in parts).strip()
        return self._safe_json_object(text)

    def _label_image_openai(self, provider, image_url: str) -> dict | None:
        api_key = os.getenv(str(provider.api_key_alias or "").strip())
        if not api_key or not image_url:
            return None
        body = {
            "model": provider.model_name,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return strict JSON only. "
                        "Fields: category, mood, image_type, subject_tags, commercial_intent, "
                        "keyword_relevance_score, text_overlay, thumbnail_score, quality_score, "
                        "is_thumbnail_candidate, confidence. "
                        "category and mood in Korean short labels. thumbnail_score 0-100. "
                        "commercial_intent 0-5. keyword_relevance_score 0-100. "
                        "subject_tags is a short Korean string array. quality_score 1-5. confidence 0-1."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Label this image for content operations."},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
        }
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        content = (((result.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        return self._safe_json_object(content)

    def _safe_json_object(self, value: str) -> dict | None:
        text = str(value or "").strip()
        if not text:
            return None
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            payload = json.loads(text)
        except Exception:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                return None
            try:
                payload = json.loads(text[start:end + 1])
            except Exception:
                return None
        return payload if isinstance(payload, dict) else None


labeling_ai_service = LabelingAIService()


def _configured_provider_id(*, prefer_paid: bool) -> int | None:
    key = LabelSettingKeys.PAID_PROVIDER_ID if prefer_paid else LabelSettingKeys.FREE_PROVIDER_ID
    raw = AppSettingRepository.get_value(key, "")
    try:
        value = int(str(raw or "").strip())
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None
