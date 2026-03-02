from __future__ import annotations


class SettingNamespaces:
    COLLECT = "collect"
    LABEL = "label"
    WRITER = "writer"
    PUBLISH = "publish"


class CollectSettingKeys:
    KEYWORD_SCOPE = "collect.keyword_scope"
    MAX_RESULTS = "collect.max_results"
    REQUEST_TIMEOUT = "collect.request_timeout"
    RETRY_COUNT = "collect.retry_count"
    INTERVAL_MINUTES = "collect.interval_minutes"
    SELECTED_CHANNEL_CODES = "collect.selected_channel_codes"
    SELECTED_CATEGORY_IDS = "collect.selected_category_ids"
    NAVER_RELATED_SYNC = "collect.naver_related_sync"


class LabelSettingKeys:
    METHOD = "label.method"
    BATCH_SIZE = "label.batch_size"
    QUALITY_THRESHOLD = "label.quality_threshold"
    RELABEL_POLICY = "label.relabel_policy"


class WriterSettingKeys:
    DEFAULT_TEMPLATE_ID = "writer.default_template_id"
    DEFAULT_PERSONA_ID = "writer.default_persona_id"
    DEFAULT_WRITING_CHANNEL_ID = "writer.default_writing_channel_id"
    SECONDARY_WRITING_CHANNEL_IDS = "writer.secondary_writing_channel_ids"
    CHANNEL_POLICIES = "writer.channel_policies"
    DEFAULT_AI_PROVIDER_ID = "writer.default_ai_provider_id"
    AI_PROVIDER_PRIORITY = "writer.ai_provider_priority"
    MIN_SOURCE_COUNT = "writer.min_source_count"
    DEFAULT_TONE = "writer.default_tone"
    DEFAULT_READER_LEVEL = "writer.default_reader_level"
    DEFAULT_LENGTH = "writer.default_length"
    CREATIVITY_LEVEL = "writer.creativity_level"
    FACTUALITY_LEVEL = "writer.factuality_level"
    SEO_KEYWORDS = "writer.seo_keywords"
    AUTO_ENABLED = "writer.auto_enabled"
    AUTO_INTERVAL_MINUTES = "writer.auto_interval_minutes"
    AUTO_BATCH_COUNT = "writer.auto_batch_count"
    AUTO_RETRY_COUNT = "writer.auto_retry_count"
    AUTO_TIME_WINDOW = "writer.auto_time_window"


class PublishSettingKeys:
    CHANNEL_MODE = "publish.channel_mode"
    CYCLE_MINUTES = "publish.cycle_minutes"
    RETRY_COUNT = "publish.retry_count"
    REQUIRE_APPROVAL = "publish.require_approval"



