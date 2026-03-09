(() => {
  const cfg = window.WebShellConfig || {};
  const STORAGE_KEY = cfg.STORAGE_KEY || "blogwriter-theme";
  const COLLECT_LOG_STORAGE_KEY = cfg.COLLECT_LOG_STORAGE_KEY || "blogwriter-collect-logs-v1";
  const COLLECT_JOB_STATE_KEY = cfg.COLLECT_JOB_STATE_KEY || "blogwriter-collect-job-state-v1";
  const WRITER_LOG_STORAGE_KEY = cfg.WRITER_LOG_STORAGE_KEY || "blogwriter-writer-logs-v1";
  const DASHBOARD_PREF_STORAGE_KEY = cfg.DASHBOARD_PREF_STORAGE_KEY || "blogwriter-dashboard-pref-v1";
  const DASHBOARD_HISTORY_STORAGE_KEY = cfg.DASHBOARD_HISTORY_STORAGE_KEY || "blogwriter-dashboard-history-v1";
  const MONITOR_RETRY_META_STORAGE_KEY = cfg.MONITOR_RETRY_META_STORAGE_KEY || "blogwriter-monitor-retry-meta-v1";
  const ENUM_LABELS = cfg.ENUM_LABELS || {};
  const sectionMap = cfg.sectionMap || {};
  const menuNodeToSection = cfg.menuNodeToSection || {};
  const sectionToDefaultNode = cfg.sectionToDefaultNode || {};

  const state = {
    section: "dashboard",
    categories: [],
    keywords: [],
    keywordPage: 1,
    keywordPageSize: 20,
    categorySort: "name_asc",
    keywordSort: "created_desc",
    keywordSearch: "",
    collectKeywords: [],
    collectCategories: [],
    collectSettingChannels: [],
    collectSettingCategories: [],
    collectSettingChannelCodes: [],
    collectSettingCategoryIds: [],
    collectSettingChannelSearch: "",
    collectSettingCategorySearch: "",
    collectSettingsSnapshot: null,
    selectedCategoryId: null,
    selectedCollectCategoryKey: null,
    selectedCollectKeywordId: null,
    collectUiBound: false,
    collectRunLogs: [],
    collectJobState: {},
    collectLatestJobs: [],
    collectPollTimer: null,
    writerRunLogs: [],
    writerStatus: { running: false, stop_requested: false },
    writerPollTimer: null,
    selectedKeywordId: null,
    selectedRelatedKeywordId: null,
    relatedSourceFilter: "all",
    relatedSyncLog: "",
    keywordSeoProfile: null,
    keywordSeoStatus: "",
    selectedChannelId: null,
    selectedContentId: null,
    selectedImageId: null,
    selectedPersonaId: null,
    personaRows: [],
    personaSearch: "",
    personaActiveFilter: "all",
    selectedTemplateId: null,
    templateRows: [],
    templateSelectedSnapshot: null,
    selectedProviderId: null,
    providerRows: [],
    selectedWriterArticleId: null,
    selectedWriterChannelId: null,
    selectedWriterSettingChannelId: null,
    writerChannelSort: "name_asc",
    writerChannelRows: [],
    writerChannelAuthSnapshot: null,
    writerChannelOriginalCode: "",
    writerBoardRows: [],
    writerBoardPage: 1,
    writerBoardPageSize: 15,
    writerBoardSearch: "",
    writerBoardStatusFilter: "all",
    writerBoardSelectedIds: [],
    writerBoardStatusHistory: {},
    writerSettingPersonaIds: [],
    writerSettingTemplateIds: [],
    writerSettingPersonaRows: [],
    writerSettingTemplateRows: [],
    writerSettingProviderRows: [],
    writerSettingChannelPolicies: {},
    writerSettingPolicyScope: "",
    selectedPublishChannelId: null,
    selectedPublishSettingChannelCode: null,
    selectedPublisherArticleId: null,
    selectedPublisherJobId: null,
    publisherJobRows: [],
    publisherJobPage: 1,
    publisherJobPageSize: 15,
    publisherHistoryStatusFilter: "all",
    publisherHistoryChannelFilter: "all",
    publisherHistorySearch: "",
    publisherHistoryFrom: "",
    publisherHistoryTo: "",
    publishSettingSearch: "",
    publishSettingSort: "name_asc",
    publishSettingSnapshotByCode: {},
    contentRows: [],
    imageRows: [],
    contentViewerEditor: null,
    writerEditor: null,
    menuTree: [],
    menuNodeId: "",
    monitorStageFilter: "all",
    monitorLevelFilter: "all",
    monitorTextFilter: "",
    monitorStreamEnabled: false,
    monitorPollSec: 5,
    monitorPollTimer: null,
    monitorCursor: "",
    monitorNextCursor: "",
    monitorCursorStack: [],
    monitorRetryMeta: {},
    monitorRetryMax: 5,
    monitorLastRows: [],
    dashboardAutoRefreshEnabled: false,
    dashboardAutoRefreshSec: 30,
    dashboardThresholds: {
      collect_fail: 20,
      writer_unready: 30,
      publish_fail: 20,
      monitor_errors: 5,
    },
    dashboardHistory: {},
    dashboardPollTimer: null,
    automationStatus: null,
    automationPollTimer: null,
    labelPollTimer: null,
    labelPollingInFlight: false,
    labelLastFailedStage: "",
    collectSettings: null,
    collectIsRunning: false,
    collectStatusSig: "",
    collectedUiBound: false,
    collectedTab: "text",
    contentPage: 1,
    contentPageSize: 15,
    contentTotal: 0,
    imagePage: 1,
    imagePageSize: 24,
    imageTotal: 0,
    selectedContentRow: null,
    selectedImageRow: null,
  };

  const qs = (s) => document.querySelector(s);
  const qsa = (s) => [...document.querySelectorAll(s)];

  function loadCollectLogState() {
    try {
      const rawLogs = localStorage.getItem(COLLECT_LOG_STORAGE_KEY);
      const logs = rawLogs ? JSON.parse(rawLogs) : [];
      state.collectRunLogs = Array.isArray(logs) ? logs.slice(0, 25).map((v) => String(v)) : [];
    } catch (_e) {
      state.collectRunLogs = [];
    }

    try {
      const rawJobState = localStorage.getItem(COLLECT_JOB_STATE_KEY);
      const jobState = rawJobState ? JSON.parse(rawJobState) : {};
      state.collectJobState = jobState && typeof jobState === "object" ? jobState : {};
    } catch (_e) {
      state.collectJobState = {};
    }
  }

  function persistCollectLogState() {
    try {
      localStorage.setItem(COLLECT_LOG_STORAGE_KEY, JSON.stringify(state.collectRunLogs.slice(0, 25)));
      localStorage.setItem(COLLECT_JOB_STATE_KEY, JSON.stringify(state.collectJobState || {}));
    } catch (_e) {
      // ignore storage errors
    }
  }

  function clearCollectLogState() {
    state.collectRunLogs = [];
    const next = {};
    (state.collectLatestJobs || []).forEach((job) => {
      const id = Number(job.id || 0);
      if (!id) return;
      const key = String(id);
      const status = String(job.status || "");
      const collected = Number(job.collected_count || 0);
      next[key] = `${status}:${collected}`;
    });
    state.collectJobState = next;
    persistCollectLogState();
  }

  function loadWriterLogState() {
    try {
      const rawLogs = localStorage.getItem(WRITER_LOG_STORAGE_KEY);
      const logs = rawLogs ? JSON.parse(rawLogs) : [];
      state.writerRunLogs = Array.isArray(logs) ? logs.slice(0, 40).map((v) => String(v)) : [];
    } catch (_e) {
      state.writerRunLogs = [];
    }
  }

  function persistWriterLogState() {
    try {
      localStorage.setItem(WRITER_LOG_STORAGE_KEY, JSON.stringify((state.writerRunLogs || []).slice(0, 40)));
    } catch (_e) {
      // ignore storage errors
    }
  }

  function appendWriterLogs(messages) {
    const next = Array.isArray(messages) ? messages : [messages];
    const stamp = new Date().toLocaleTimeString("ko-KR", { hour12: false });
    next.forEach((msg) => state.writerRunLogs.unshift(`[${stamp}] ${String(msg || "")}`));
    state.writerRunLogs = state.writerRunLogs.slice(0, 40);
    persistWriterLogState();
    renderWriterLogDashboard();
    refreshWriterRunChannelMetricHint();
  }

  function clearWriterLogState() {
    state.writerRunLogs = [];
    persistWriterLogState();
    renderWriterLogDashboard();
    refreshWriterRunChannelMetricHint();
  }

  function loadMonitorRetryMeta() {
    try {
      const raw = localStorage.getItem(MONITOR_RETRY_META_STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : {};
      state.monitorRetryMeta = parsed && typeof parsed === "object" ? parsed : {};
    } catch (_e) {
      state.monitorRetryMeta = {};
    }
  }

  function persistMonitorRetryMeta() {
    try {
      localStorage.setItem(MONITOR_RETRY_META_STORAGE_KEY, JSON.stringify(state.monitorRetryMeta || {}));
    } catch (_e) {
      // ignore
    }
  }

  function downloadTextFile(filename, content, mimeType = "text/plain;charset=utf-8") {
    const blob = new Blob([String(content || "")], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function downloadWriterLogsTxt() {
    const lines = [...(state.writerRunLogs || [])].reverse();
    downloadTextFile(`writer-run-${new Date().toISOString().slice(0, 10)}.txt`, `${lines.join("\n")}\n`);
  }

  function csvEscape(value) {
    const text = String(value ?? "");
    if (!/[",\n]/.test(text)) return text;
    return `"${text.replace(/"/g, '""')}"`;
  }

  function downloadWriterLogsCsv() {
    const lines = [...(state.writerRunLogs || [])].reverse();
    const rows = ["timestamp,message"];
    lines.forEach((line) => {
      const m = String(line || "").match(/^\[(.*?)\]\s*(.*)$/);
      const ts = m ? m[1] : "";
      const msg = m ? m[2] : String(line || "");
      rows.push(`${csvEscape(ts)},${csvEscape(msg)}`);
    });
    downloadTextFile(`writer-run-${new Date().toISOString().slice(0, 10)}.csv`, `${rows.join("\n")}\n`, "text/csv;charset=utf-8");
  }

  function refreshWriterRunChannelMetricHint() {
    const hint = qs("#writerRunChannelMetricHint");
    if (!hint) return;
    const lines = state.writerRunLogs || [];
    const bucket = {};
    lines.forEach((line) => {
      const msg = String(line || "");
      const m = msg.match(/\]\s+\[\d+\/\d+\]\s+(.+?)\s+\d+\/\d+:\s+생성\s+(완료|실패)/);
      if (!m) return;
      const channel = String(m[1] || "-");
      const status = String(m[2] || "");
      if (!bucket[channel]) bucket[channel] = { ok: 0, fail: 0 };
      if (status.includes("완료")) bucket[channel].ok += 1;
      else bucket[channel].fail += 1;
    });
    const parts = Object.entries(bucket).map(([channel, stat]) => {
      const total = Number(stat.ok || 0) + Number(stat.fail || 0);
      const failRate = total ? ((Number(stat.fail || 0) / total) * 100).toFixed(1) : "0.0";
      return `${channel}: ${total}건(실패 ${failRate}%)`;
    });
    hint.textContent = parts.length ? `채널별 처리량/실패율 | ${parts.join(" | ")}` : "채널별 처리량/실패율 데이터 없음";
  }

  const dialogModule = window.createDialogModule({ qs });
  const {
    showAlert,
    showConfirm,
    showActionAlert,
  } = dialogModule;

  const commonModule = window.createCommonModule({ qs });
  const {
    selectValueIfExists,
    fmt,
    yn,
    request,
    clearFieldError,
    setFieldError,
    clearFieldErrors,
    applyFieldErrors,
    syncSelectOptions,
  } = commonModule;

  const nativeSelectModule = window.createNativeSelectModule({ qsa });
  const {
    setupNativeSelectProxies,
  } = nativeSelectModule;

  const shellModule = window.createShellModule({
    qs,
    state,
    request,
    STORAGE_KEY,
    sectionMap,
    menuNodeToSection,
    sectionToDefaultNode,
  });
  const {
    applyTheme,
    getInitialTheme,
    isDesktopEmbed,
    navigateToNode,
    renderV2Menus,
    initV2Menus,
    setupSectionShell,
  } = shellModule;

  function renderCategoryTable() {
    const tbody = qs("#categoryTable tbody");
    if (!tbody) return;
    tbody.innerHTML = "";
    const rows = getSortedCategories(state.categories || []);
    if (!rows.length) {
      tbody.innerHTML = "<tr><td colspan='2'>카테고리 없음</td></tr>";
      return;
    }
    rows.forEach((c) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${c.id}</td><td>${c.name}</td>`;
      tr.addEventListener("click", () => {
        state.selectedCategoryId = c.id;
        state.keywordPage = 1;
        state.selectedKeywordId = null;
        syncCategorySelection();
        renderCategoryTable();
        renderKeywordTable();
        syncSourceKeywordSelect();
        loadRelatedSection();
      });
      if (state.selectedCategoryId === c.id) tr.classList.add("selected");
      tbody.appendChild(tr);
    });
  }

  function syncCategorySelection() {
    const select = qs("#keywordCategorySelect");
    if (!select) return;
    const rows = getSortedCategories(state.categories || []);
    if (!state.selectedCategoryId && rows.length) state.selectedCategoryId = rows[0].id;
    syncSelectOptions(select, rows, (c) => c.id, (c) => c.name, state.selectedCategoryId);
  }

  function getSortedCategories(rows) {
    const list = Array.isArray(rows) ? [...rows] : [];
    const mode = String(state.categorySort || "name_asc");
    if (mode === "name_desc") return list.sort((a, b) => String(b.name || "").localeCompare(String(a.name || ""), "ko"));
    if (mode === "id_desc") return list.sort((a, b) => Number(b.id || 0) - Number(a.id || 0));
    if (mode === "id_asc") return list.sort((a, b) => Number(a.id || 0) - Number(b.id || 0));
    return list.sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), "ko"));
  }

  function getFilteredKeywords() {
    if (!state.selectedCategoryId) return [];
    const search = String(state.keywordSearch || "").trim().toLowerCase();
    let rows = state.keywords.filter((k) => k.category_id === state.selectedCategoryId);
    if (search) {
      rows = rows.filter((k) => {
        const hay = `${k.keyword || ""} ${k.category_name || ""}`.toLowerCase();
        return hay.includes(search);
      });
    }
    return getSortedKeywords(rows);
  }

  function getSortedKeywords(rows) {
    const list = Array.isArray(rows) ? [...rows] : [];
    const mode = String(state.keywordSort || "created_desc");
    if (mode === "keyword_asc") return list.sort((a, b) => String(a.keyword || "").localeCompare(String(b.keyword || ""), "ko"));
    if (mode === "keyword_desc") return list.sort((a, b) => String(b.keyword || "").localeCompare(String(a.keyword || ""), "ko"));
    if (mode === "collected_desc") return list.sort((a, b) => Number(b.total_collected_count || 0) - Number(a.total_collected_count || 0));
    if (mode === "published_desc") return list.sort((a, b) => Number(b.total_published_count || 0) - Number(a.total_published_count || 0));
    if (mode === "active_first") return list.sort((a, b) => Number(!!b.is_active) - Number(!!a.is_active));
    return list.sort((a, b) => Number(b.id || 0) - Number(a.id || 0));
  }

  function renderKeywordPager(totalCount, totalPages) {
    const wrap = qs("#keywordPager");
    if (!wrap) return;
    wrap.innerHTML = "";

    const info = document.createElement("span");
    info.className = "pager-info";
    if (!totalCount) {
      info.textContent = "0개";
      wrap.appendChild(info);
      return;
    }

    const current = Math.min(Math.max(1, state.keywordPage), totalPages);
    info.textContent = `총 ${totalCount}개 / ${current} / ${totalPages} 페이지`;

    const prevBtn = document.createElement("button");
    prevBtn.type = "button";
    prevBtn.className = "btn ghost";
    prevBtn.textContent = "이전";
    prevBtn.disabled = current <= 1;
    prevBtn.addEventListener("click", () => {
      if (state.keywordPage <= 1) return;
      state.keywordPage -= 1;
      renderKeywordTable();
    });

    const nextBtn = document.createElement("button");
    nextBtn.type = "button";
    nextBtn.className = "btn ghost";
    nextBtn.textContent = "다음";
    nextBtn.disabled = current >= totalPages;
    nextBtn.addEventListener("click", () => {
      if (state.keywordPage >= totalPages) return;
      state.keywordPage += 1;
      renderKeywordTable();
    });

    wrap.appendChild(prevBtn);
    wrap.appendChild(nextBtn);
    wrap.appendChild(info);
  }

  function renderKeywordTable() {
    const tbody = qs("#keywordTable tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    const filtered = getFilteredKeywords();
    if (state.selectedKeywordId && !filtered.some((x) => x.id === state.selectedKeywordId)) {
      state.selectedKeywordId = null;
    }
    if (!state.selectedKeywordId && filtered.length) {
      state.selectedKeywordId = filtered[0].id;
    }

    const totalCount = filtered.length;
    const totalPages = Math.max(1, Math.ceil(totalCount / state.keywordPageSize));
    state.keywordPage = Math.min(Math.max(1, state.keywordPage), totalPages);
    const start = (state.keywordPage - 1) * state.keywordPageSize;
    const pageRows = filtered.slice(start, start + state.keywordPageSize);

    if (!totalCount) {
      const hasSearch = !!String(state.keywordSearch || "").trim();
      tbody.innerHTML = `<tr><td colspan='8'>${hasSearch ? "검색 조건에 맞는 키워드 없음" : "카테고리에 키워드 없음"}</td></tr>`;
      renderKeywordPager(0, 1);
      return;
    }

    pageRows.forEach((k) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${k.id}</td><td>${k.keyword}</td><td>${k.category_name || "-"}</td><td>${yn(k.is_active)}</td><td>${k.total_collected_count ?? 0}</td><td>${fmt(k.last_collected_at)}</td><td>${k.total_published_count ?? 0}</td><td>${fmt(k.last_published_at)}</td>`;
      tr.addEventListener("click", () => {
        state.selectedKeywordId = k.id;
        if (k.category_id) state.selectedCategoryId = k.category_id;
        const categorySelect = qs("#keywordCategorySelect");
        const sourceSelect = qs("#sourceKeywordSelect");
        if (categorySelect && state.selectedCategoryId != null) categorySelect.value = String(state.selectedCategoryId);
        if (sourceSelect) sourceSelect.value = String(k.id);
        renderKeywordTable();
        renderCategoryTable();
        syncSourceKeywordSelect();
        loadRelatedSection();
        loadKeywordSeoProfile(k.id).catch((e) => showAlert(String(e), "오류", "error"));
      });
      if (state.selectedKeywordId === k.id) tr.classList.add("selected");
      tbody.appendChild(tr);
    });

    renderKeywordPager(totalCount, totalPages);
  }

  function syncSourceKeywordSelect() {
    const select = qs("#sourceKeywordSelect");
    if (!select) return;
    const filtered = getFilteredKeywords();
    if (!state.selectedKeywordId && filtered.length) state.selectedKeywordId = filtered[0].id;
    if (state.selectedKeywordId && !filtered.some((x) => x.id === state.selectedKeywordId)) state.selectedKeywordId = null;
    syncSelectOptions(select, filtered, (k) => k.id, (k) => k.keyword, state.selectedKeywordId);
  }

  async function loadCategories() {
    state.categories = await request("/api/categories");
    renderCategoryTable();
    syncCategorySelection();
  }

  async function loadKeywords() {
    state.keywords = await request("/api/keywords");
    if (state.selectedKeywordId && !state.keywords.some((x) => x.id === state.selectedKeywordId)) state.selectedKeywordId = null;
    renderKeywordTable();
    syncSourceKeywordSelect();
    await loadKeywordSeoProfile(state.selectedKeywordId, { silent: true });
  }

  async function loadRelatedLimit() {
    const data = await request("/api/settings/related-keyword-limit");
    const badge = qs("#relatedLimitBadge");
    if (badge) badge.textContent = `현재 상한: ${data.limit}개`;
  }

  async function loadRelatedSection() {
    const sourceId = Number(qs("#sourceKeywordSelect")?.value || 0);
    const relatedBody = qs("#relatedTable tbody");
    const sourceFilter = String(qs("#relatedSourceFilter")?.value || state.relatedSourceFilter || "all");

    if (!sourceId) {
      if (relatedBody) relatedBody.innerHTML = "<tr><td colspan='6'>원본 키워드 없음</td></tr>";
      return;
    }

    const related = await request(`/api/related?source_keyword_id=${sourceId}`);
    const sourceOptions = ["all", ...new Set((related || []).map((r) => String(r.source_type || "").trim()).filter(Boolean))];
    const sourceSelect = qs("#relatedSourceFilter");
    if (sourceSelect) {
      const prev = sourceFilter;
      sourceSelect.innerHTML = "";
      sourceOptions.forEach((value) => {
        const opt = document.createElement("option");
        opt.value = value;
        opt.textContent = value === "all" ? "전체" : value;
        sourceSelect.appendChild(opt);
      });
      sourceSelect.value = sourceOptions.includes(prev) ? prev : "all";
      state.relatedSourceFilter = sourceSelect.value;
    }
    const filteredRelated = (related || []).filter((r) => state.relatedSourceFilter === "all" || String(r.source_type || "") === state.relatedSourceFilter);
    if (relatedBody) {
      relatedBody.innerHTML = filteredRelated.length ? "" : "<tr><td colspan='6'>연관키워드 없음</td></tr>";
      filteredRelated.forEach((r) => {
        const tr = document.createElement("tr");
        tr.className = r.is_active ? "related-row is-active" : "related-row is-inactive";
        const statusLabel = r.is_active ? "활성" : "비활성";
        tr.innerHTML = `
          <td>${r.relation_id}</td>
          <td>${r.related_keyword}</td>
          <td>${r.source_type || "-"}</td>
          <td>
            <label class="switch related-switch" data-on="${r.is_active ? "true" : "false"}" aria-label="${r.related_keyword} 상태">
              <input type="checkbox" ${r.is_active ? "checked" : ""} data-related-id="${r.related_keyword_id}" />
              <span class="switch-slider"></span>
            </label>
            <span class="related-status-chip ${r.is_active ? "is-active" : "is-inactive"}">${statusLabel}</span>
          </td>
          <td>${r.collect_count}</td>
          <td>${fmt(r.last_seen_at)}</td>
        `;
        tr.addEventListener("click", () => {
          state.selectedRelatedKeywordId = r.related_keyword_id;
          qsa("#relatedTable tbody tr").forEach((el) => el.classList.remove("selected"));
          tr.classList.add("selected");
        });
        const checkbox = tr.querySelector("input[type='checkbox']");
        checkbox?.addEventListener("click", (event) => event.stopPropagation());
        checkbox?.addEventListener("change", async (event) => {
          event.stopPropagation();
          const target = event.currentTarget;
          target.disabled = true;
          try {
            await toggleRelatedKeyword(r.related_keyword_id, false);
          } catch (error) {
            target.checked = !target.checked;
            showAlert(String(error), "오류", "error");
          } finally {
            target.disabled = false;
          }
        });
        relatedBody.appendChild(tr);
      });
    }
    const logNode = qs("#relatedSyncLog");
    if (logNode) logNode.textContent = state.relatedSyncLog || `연관키워드 ${filteredRelated.length}건 표시 / 전체 ${related.length}건`;
  }

  function renderChipList(targetSelector, items, emptyLabel = "-") {
    const node = qs(targetSelector);
    if (!node) return;
    node.innerHTML = "";
    const values = Array.isArray(items) ? items.filter((item) => String(item || "").trim()) : [];
    if (!values.length) {
      const span = document.createElement("span");
      span.className = "chip";
      span.textContent = emptyLabel;
      node.appendChild(span);
      return;
    }
    values.forEach((item) => {
      const span = document.createElement("span");
      span.className = "chip";
      span.textContent = String(item);
      node.appendChild(span);
    });
  }

  function renderKeywordSeoPanel(profilePayload = null) {
    const profile = profilePayload || null;
    state.keywordSeoProfile = profile;
    const emptyNode = qs("#keywordSeoEmpty");
    const panelNode = qs("#keywordSeoPanel");
    const statusNode = qs("#keywordSeoStatus");
    if (statusNode) {
      statusNode.textContent = state.keywordSeoStatus || (profile ? `최근 분석 ${fmt(profile.analyzed_at)}` : "분석 전입니다.");
    }
    if (!profile) {
      if (emptyNode) emptyNode.classList.remove("hidden");
      if (panelNode) panelNode.classList.add("hidden");
      renderChipList("#keywordSeoSections", [], "데이터 없음");
      renderChipList("#keywordSeoTerms", [], "데이터 없음");
      const summaryNode = qs("#keywordSeoSummary");
      if (summaryNode) summaryNode.textContent = "-";
      ["#keywordSeoSampleCount", "#keywordSeoLengthRange", "#keywordSeoHeadingCount", "#keywordSeoImageCount", "#keywordSeoFormat", "#keywordSeoAnalyzedAt"].forEach((selector) => {
        const node = qs(selector);
        if (node) node.textContent = "-";
      });
      return;
    }
    if (emptyNode) emptyNode.classList.add("hidden");
    if (panelNode) panelNode.classList.remove("hidden");
    const lengthRange = profile.recommended_length_min && profile.recommended_length_max
      ? `${profile.recommended_length_min} ~ ${profile.recommended_length_max}자`
      : "-";
    const setText = (selector, value) => {
      const node = qs(selector);
      if (node) node.textContent = value;
    };
    setText("#keywordSeoSampleCount", `${profile.sample_count || 0}건`);
    setText("#keywordSeoLengthRange", lengthRange);
    setText("#keywordSeoHeadingCount", profile.recommended_heading_count != null ? `${profile.recommended_heading_count}개` : "-");
    setText("#keywordSeoImageCount", profile.recommended_image_count != null ? `${profile.recommended_image_count}개` : "-");
    setText("#keywordSeoFormat", profile.dominant_format || "-");
    setText("#keywordSeoAnalyzedAt", fmt(profile.analyzed_at));
    const summaryNode = qs("#keywordSeoSummary");
    if (summaryNode) summaryNode.textContent = profile.summary_text || "-";
    renderChipList("#keywordSeoSections", profile.common_sections || [], "섹션 없음");
    renderChipList("#keywordSeoTerms", profile.common_terms || [], "표현 없음");
  }

  async function loadKeywordSeoProfile(keywordId = null, { silent = false } = {}) {
    const targetId = Number(keywordId || state.selectedKeywordId || 0);
    if (!targetId) {
      state.keywordSeoStatus = "선택된 키워드가 없습니다.";
      renderKeywordSeoPanel(null);
      return;
    }
    if (!silent) {
      state.keywordSeoStatus = "SEO 패턴을 불러오는 중입니다.";
      renderKeywordSeoPanel(state.keywordSeoProfile);
    }
    const result = await request(`/api/keywords/${targetId}/seo-profile`);
    state.keywordSeoStatus = result?.profile ? `최근 분석 ${fmt(result.profile.analyzed_at)}` : "저장된 SEO 패턴이 없습니다.";
    renderKeywordSeoPanel(result?.profile || null);
  }

  async function analyzeKeywordSeoProfile() {
    const targetId = Number(state.selectedKeywordId || 0);
    if (!targetId) return showAlert("분석할 키워드를 선택하세요.");
    const sampleLimit = Number(qs("#keywordSeoSampleLimit")?.value || 12);
    state.keywordSeoStatus = "SEO 패턴을 분석 중입니다.";
    renderKeywordSeoPanel(state.keywordSeoProfile);
    const result = await request(`/api/keywords/${targetId}/seo-profile/analyze`, {
      method: "POST",
      body: JSON.stringify({ sample_limit: sampleLimit }),
    });
    state.keywordSeoStatus = `[${fmt(new Date().toISOString())}] SEO 패턴 분석 완료 / 샘플 ${result.sample_count || 0}건`;
    renderKeywordSeoPanel(result?.profile || null);
    showAlert("SEO 패턴 분석이 완료되었습니다.", "성공", "success");
  }

  async function refreshKeywordSection() {
    const [categories, keywords, relatedLimit] = await Promise.all([
      request("/api/categories"),
      request("/api/keywords"),
      request("/api/settings/related-keyword-limit"),
    ]);
    state.categories = categories;
    state.keywords = keywords;
    if (!state.keywordPage || state.keywordPage < 1) state.keywordPage = 1;
    if (state.selectedCategoryId && !state.categories.some((x) => x.id === state.selectedCategoryId)) state.selectedCategoryId = null;
    if (state.selectedKeywordId && !state.keywords.some((x) => x.id === state.selectedKeywordId)) state.selectedKeywordId = null;
    renderCategoryTable();
    syncCategorySelection();
    renderKeywordTable();
    syncSourceKeywordSelect();
    const badge = qs("#relatedLimitBadge");
    if (badge) badge.textContent = `현재 상한: ${relatedLimit.limit}개`;
    await loadRelatedSection();
    await loadKeywordSeoProfile(state.selectedKeywordId, { silent: true });
  }

  async function addCategory() {
    const name = String(qs("#categoryInput")?.value || "").trim();
    if (!name) return showAlert("카테고리 이름을 입력하세요.");
    await request("/api/categories", { method: "POST", body: JSON.stringify({ name }) });
    qs("#categoryInput").value = "";
    await loadCategories();
    showAlert("카테고리가 추가되었습니다.", "성공", "success");
  }

  async function renameCategory() {
    if (!state.selectedCategoryId) return showAlert("수정할 카테고리를 선택하세요.");
    const name = String(qs("#categoryInput")?.value || "").trim();
    if (!name) return showAlert("변경할 카테고리 이름을 입력하세요.");
    await request(`/api/categories/${state.selectedCategoryId}/update`, {
      method: "POST",
      body: JSON.stringify({ name }),
    });
    await loadCategories();
    await loadKeywords();
    showAlert("카테고리 이름이 변경되었습니다.", "성공", "success");
  }

  async function deleteCategory() {
    if (!state.selectedCategoryId) return showAlert("삭제할 카테고리를 선택하세요.");
    const category = (state.categories || []).find((c) => Number(c.id) === Number(state.selectedCategoryId));
    const affected = (state.keywords || []).filter((k) => Number(k.category_id || 0) === Number(state.selectedCategoryId)).length;
    const ok = await showConfirm(`카테고리 '${category?.name || state.selectedCategoryId}'를 삭제하시겠습니까?\n영향 키워드: ${affected}건`, "삭제 확인", "warn");
    if (!ok) return;
    await request(`/api/categories/${state.selectedCategoryId}`, { method: "DELETE" });
    state.selectedCategoryId = null;
    await refreshKeywordSection();
    showAlert("카테고리가 삭제되었습니다.", "성공", "success");
  }

  async function addKeyword() {
    const categoryId = Number(qs("#keywordCategorySelect")?.value || 0);
    const keyword = String(qs("#keywordInput")?.value || "").trim();
    if (!categoryId) return showAlert("카테고리를 선택하세요.");
    if (!keyword) return showAlert("키워드를 입력하세요.");
    const exists = (state.keywords || []).some((k) => String(k.keyword || "").trim().toLowerCase() === keyword.toLowerCase());
    if (exists) return showAlert("이미 등록된 키워드입니다.", "중복", "warn");
    await request("/api/keywords", { method: "POST", body: JSON.stringify({ category_id: categoryId, keyword }) });
    qs("#keywordInput").value = "";
    await loadKeywords();
    await loadRelatedSection();
    showAlert("키워드가 추가되었습니다.", "성공", "success");
  }

  async function addKeywordBulk() {
    const categoryId = Number(qs("#keywordCategorySelect")?.value || 0);
    const raw = String(qs("#keywordBulkInput")?.value || "").trim();
    if (!categoryId) return showAlert("카테고리를 선택하세요.");
    if (!raw) return showAlert("일괄 등록할 키워드를 입력하세요.");
    const parts = raw.split(/[\n,]/g).map((v) => v.trim()).filter(Boolean);
    if (!parts.length) return showAlert("유효한 키워드가 없습니다.");
    const deduped = [...new Set(parts.map((v) => v.toLowerCase()))];
    const originalByLower = {};
    parts.forEach((v) => {
      const key = v.toLowerCase();
      if (!originalByLower[key]) originalByLower[key] = v;
    });
    const keywords = deduped.map((k) => originalByLower[k]);
    const existing = new Set((state.keywords || []).map((k) => String(k.keyword || "").trim().toLowerCase()));
    const newItems = keywords.filter((k) => !existing.has(String(k || "").toLowerCase()));
    const duplicated = keywords.length - newItems.length;
    if (!newItems.length) return showAlert("모든 키워드가 이미 등록되어 있습니다.", "중복", "warn");
    const ok = await showConfirm(`일괄 추가를 진행할까요?\n신규: ${newItems.length}건 / 중복 제외: ${duplicated}건`, "일괄 추가", "warn");
    if (!ok) return;
    const result = await request("/api/keywords/bulk", {
      method: "POST",
      body: JSON.stringify({ category_id: categoryId, keywords: newItems }),
    });
    if (qs("#keywordBulkInput")) qs("#keywordBulkInput").value = "";
    await loadKeywords();
    await loadRelatedSection();
    showAlert(`일괄 추가 완료\n추가: ${result.added || 0}건 / 중복: ${result.duplicated || 0}건 / 무효: ${result.invalid || 0}건`, "성공", "success");
  }

  async function toggleKeyword() {
    if (!state.selectedKeywordId) return showAlert("키워드를 선택하세요.");
    await request(`/api/keywords/${state.selectedKeywordId}/toggle`, { method: "POST", body: "{}" });
    await loadKeywords();
    showAlert("키워드 상태가 변경되었습니다.", "성공", "success");
  }

  async function toggleKeywordBatch() {
    const filtered = getFilteredKeywords();
    if (!filtered.length) return showAlert("현재 필터 결과가 없습니다.");
    const ok = await showConfirm(`현재 필터 결과 ${filtered.length}건의 활성/비활성을 일괄 전환할까요?`, "일괄 전환", "warn");
    if (!ok) return;
    const ids = filtered.map((k) => Number(k.id)).filter((n) => Number.isFinite(n));
    const result = await request("/api/keywords/toggle-batch", {
      method: "POST",
      body: JSON.stringify({ keyword_ids: ids }),
    });
    await loadKeywords();
    showAlert(`일괄 전환 완료: ${result.toggled || 0}건`, "성공", "success");
  }

  async function deleteKeyword() {
    if (!state.selectedKeywordId) return showAlert("키워드를 선택하세요.");
    await request(`/api/keywords/${state.selectedKeywordId}`, { method: "DELETE" });
    state.selectedKeywordId = null;
    await loadKeywords();
    await loadRelatedSection();
  }

  async function toggleRelatedKeyword(relatedKeywordId = null, shouldNotify = true) {
    const targetId = Number(relatedKeywordId || state.selectedRelatedKeywordId || 0);
    if (!targetId) return showAlert("연관키워드를 선택하세요.");
    await request("/api/related/toggle", {
      method: "POST",
      body: JSON.stringify({ related_keyword_id: targetId }),
    });
    await loadKeywords();
    await loadRelatedSection();
    if (shouldNotify) showAlert("연관키워드 상태가 변경되었습니다.", "성공", "success");
  }

  async function syncRelatedKeywords() {
    const sourceId = Number(qs("#sourceKeywordSelect")?.value || 0);
    if (!sourceId) return showAlert("원본 키워드를 선택하세요.");
    const sourceKeyword = (state.keywords || []).find((x) => Number(x.id) === sourceId)?.keyword || String(sourceId);
    const ok = await showConfirm(`'${sourceKeyword}' 기준으로 연관키워드를 수집할까요?`, "연관키워드 수집", "warn");
    if (!ok) return;
    const result = await request("/api/related/sync", {
      method: "POST",
      body: JSON.stringify({ source_keyword_id: sourceId }),
    });
    await loadKeywords();
    const detail = Object.entries(result.by_source || {}).map(([k, v]) => `${k}:${v}`).join(", ");
    state.relatedSyncLog = `[${fmt(new Date().toISOString())}] 원본 '${sourceKeyword}' 수집 완료 / 반영 ${result.applied || 0}건${detail ? ` / ${detail}` : ""}`;
    await loadRelatedSection();
    showAlert(`연관키워드 수집 완료\n반영: ${result.applied || 0}건${detail ? `\n소스: ${detail}` : ""}`, "완료", "success");
  }

  function renderChannelTable(rows) {
    const tbody = qs("#channelTable tbody");
    if (!tbody) return;
    tbody.innerHTML = rows.length ? "" : "<tr><td colspan='4'>채널 없음</td></tr>";
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.id}</td><td>${r.code}</td><td>${r.display_name}</td><td>${yn(r.is_enabled)}</td>`;
      tr.addEventListener("click", () => {
        state.selectedChannelId = r.id;
        qsa("#channelTable tbody tr").forEach((el) => el.classList.remove("selected"));
        tr.classList.add("selected");
      });
      if (state.selectedChannelId === r.id) tr.classList.add("selected");
      tbody.appendChild(tr);
    });
  }

  const collectionUiModule = window.createCollectionUiModule({
    qs,
    state,
  });
  const {
    setupCollectionSelectUi,
    renderCollectFilters,
    scopeLabel,
    renderCollectSummary,
  } = collectionUiModule;

  const collectionRunModule = window.createCollectionRunModule({
    qs,
    state,
    request,
    showAlert,
    showConfirm,
    renderCollectFilters,
    renderCollectSummary,
    scopeLabel,
    persistCollectLogState,
  });
  const {
    renderCollectLogDashboard,
    appendCollectLogs,
    stopCollect,
    stopCollectionPolling,
    startCollectionPolling,
    refreshCollectionSection,
    runCollect,
  } = collectionRunModule;

  const writerRunModule = window.createWriterRunModule({
    qs,
    state,
    request,
    fmt,
    selectValueIfExists,
    showAlert,
    appendWriterLogs,
    refreshWriterRunChannelMetricHint,
  });
  const {
    renderWriterLogDashboard,
    updateWriterRunControls,
    refreshWriterRunSummary,
    refreshWriterResultBoard,
    renderWriterBoardPager,
    renderWriterBoardTable,
    publishWriterBoardArticle,
    bulkPublishWriterBoardArticles,
    bulkUpdateWriterBoardStatus,
    openWriterArticleEditor,
    openWriterArticleViewer,
    closeWriterArticleEditor,
    closeWriterArticleViewer,
    saveWriterArticleEditor,
    regenerateWriterArticle,
    runWriter,
    stopWriter,
    startWriterPolling,
    stopWriterPolling,
  } = writerRunModule;

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  const collectedDataModule = window.createCollectedDataModule({
    qs,
    state,
    request,
    fmt,
    showAlert,
    escapeHtml,
  });
  const {
    switchCollectedTab,
    refreshCollectedDataSection,
    bindCollectedUi,
  } = collectedDataModule;


  function selectRow(tableSelector, tr) {
    qsa(`${tableSelector} tbody tr`).forEach((el) => el.classList.remove("selected"));
    tr.classList.add("selected");
  }

  function appendLog(tableId, message) {
    const tbody = qs(`#${tableId} tbody`);
    if (!tbody) return;
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${message}</td>`;
    tbody.prepend(tr);
  }

  async function safeRequest(url) {
    try {
      const data = await request(url);
      return { ok: true, data, error: null };
    } catch (error) {
      return { ok: false, data: null, error: String(error) };
    }
  }

  const dashboardModule = window.createDashboardModule({
    qs,
    state,
    fmt,
    safeRequest,
    navigateToNode,
    DASHBOARD_PREF_STORAGE_KEY,
    DASHBOARD_HISTORY_STORAGE_KEY,
  });
  const {
    renderAutomationStatus,
    refreshAutomationStatus,
    startAutomationPolling,
    dashboardReadPrefs,
    dashboardWritePrefs,
    dashboardBindControls,
    dashboardApplyControlValues,
    stopDashboardPolling,
    startDashboardPolling,
    dashboardSparkline,
    dashboardPushHistory,
    refreshDashboardSection,
  } = dashboardModule;

  function clampInt(value, min, max, fallback) {
    const n = Number(value);
    if (!Number.isFinite(n)) return fallback;
    return Math.max(min, Math.min(max, Math.round(n)));
  }

  const labelingModule = window.createLabelingModule({
    qs,
    state,
    request,
    safeRequest,
    appendLog,
    showAlert,
    clampInt,
  });
  const {
    labelingPresetValues,
    labelSettingDraft,
    applyLabelSettingToForm,
    syncLabelSettingModeUi,
    updateRetryLabelingButton,
    refreshLabelSettingHints,
    refreshLabelingSection,
    stopLabelingPolling,
    startLabelingPolling,
    runLabelingStage,
    retryFailedLabelingRun,
    refreshLabelSettingsSection,
    saveLabelSettingsSection,
    tickAutoLabeling,
  } = labelingModule;

  const manageModule = window.createManageModule({
    qs,
    qsa,
    state,
    request,
    safeRequest,
    showAlert,
    escapeHtml,
  });
  const {
    refreshPersonaSection,
    personaPayload,
    personaPreviewText,
    refreshPersonaCollisionHint,
    refreshTemplateSection,
    templatePayload,
    showTemplateDiff,
    cloneTemplateAsNewVersion,
    runTemplateTest,
    refreshProviderSection,
    providerPayload,
    refreshProviderAliasHint,
    normalizeProviderPriorities,
    healthCheckProvider,
    fillPersonaForm,
    fillTemplateForm,
    fillProviderForm,
    syncManageSwitchVisual,
    syncManageSwitchVisuals,
  } = manageModule;

  const collectSettingsModule = window.createCollectSettingsModule({
    qs,
    state,
    request,
    showAlert,
    showConfirm,
  });
  const {
    getCollectScopeValue,
    setCollectScopeValue,
    getCollectChecklistRows,
    getCollectSettingPayload,
    validateCollectSettingInputs,
    normalizeCollectSettingSnapshot,
    collectSettingDiffLines,
    refreshCollectSettingHints,
    renderKeywordSourceChecklist,
    updateCollectChecklistMeta,
    renderCollectChecklist,
    toggleCollectChecklistAll,
    refreshCollectSettingsSection,
    saveCollectSettingsSection,
  } = collectSettingsModule;

  function toNullableNumber(value) {
    const n = Number(value);
    return Number.isFinite(n) && n > 0 ? n : null;
  }
  const writerChannelModule = window.createWriterChannelModule({
    qs,
    state,
    ENUM_LABELS,
  });
  const {
    encodeWriterAuthReference,
    decodeWriterAuthReference,
    maskedSecret,
    writerChannelPayload,
    validateWriterChannelPayload,
    fillWriterChannelForm,
    resetWriterChannelFormForCreate,
    syncWriterChannelCodePolicy,
    syncWriterAuthChangeHint,
    syncWriterAffiliateTextState,
    syncWriterSwitchVisual,
    syncWriterChannelSwitches,
    writerChannelTypeLabel,
    writerChannelConnectionLabel,
    writerChannelStatusLabel,
    writerChannelStatusClass,
  } = writerChannelModule;

  function writerPolicyDefaults() {
    return {
      persona_ids: [],
      template_ids: [],
      persona_cursor: 0,
      template_cursor: 0,
      default_ai_provider_id: null,
      min_source_count: 3,
      default_tone: "informative",
      default_reader_level: "general",
      default_length: "medium",
      creativity_level: 3,
      factuality_level: 4,
      seo_keywords: "",
      auto_enabled: false,
      auto_interval_minutes: 1440,
      auto_batch_count: 1,
      auto_retry_count: 1,
      auto_time_window: "00:00-23:59",
    };
  }

  function writerPolicyKeyForScope(scope) {
    return String(scope || "");
  }

  function writerChannelIdFromScope(scope) {
    const text = String(scope || "");
    if (!text.startsWith("channel:")) return null;
    const id = Number(text.slice(8));
    return Number.isFinite(id) && id > 0 ? id : null;
  }

  function writerCurrentScopeFromNode() {
    return state.writerSettingPolicyScope || "";
  }

  function mergeWriterPolicy(base, overrides) {
    return { ...writerPolicyDefaults(), ...(base || {}), ...(overrides || {}) };
  }

  function getCurrentWriterPolicy() {
    const policies = state.writerSettingChannelPolicies || {};
    const scope = writerCurrentScopeFromNode();
    if (!scope) return mergeWriterPolicy(writerPolicyDefaults(), {});
    return mergeWriterPolicy(writerPolicyDefaults(), policies[writerPolicyKeyForScope(scope)]);
  }

  function syncWriterPolicyFormFromScope() {
    const p = getCurrentWriterPolicy();
    state.writerSettingPersonaIds = Array.isArray(p.persona_ids) ? p.persona_ids.map((v) => Number(v)).filter((v) => Number.isFinite(v)) : [];
    state.writerSettingTemplateIds = Array.isArray(p.template_ids) ? p.template_ids.map((v) => Number(v)).filter((v) => Number.isFinite(v)) : [];
    qs("#writerSettingMinSource").value = p.min_source_count ?? 3;
    qs("#writerSettingTone").value = p.default_tone || "informative";
    qs("#writerSettingReaderLevel").value = p.default_reader_level || "general";
    qs("#writerSettingLength").value = p.default_length || "medium";
    qs("#writerSettingCreativity").value = p.creativity_level ?? 3;
    qs("#writerSettingFactuality").value = p.factuality_level ?? 4;
    qs("#writerSettingSeoKeywords").value = p.seo_keywords || "";
    qs("#writerSettingAutoEnabled").checked = !!p.auto_enabled;
    qs("#writerSettingAutoInterval").value = p.auto_interval_minutes ?? 1440;
    qs("#writerSettingAutoBatch").value = p.auto_batch_count ?? 1;
    qs("#writerSettingAutoRetry").value = p.auto_retry_count ?? 1;
    qs("#writerSettingAutoWindow").value = p.auto_time_window || "00:00-23:59";
    selectValueIfExists(qs("#writerSettingAiProviderId"), String(p.default_ai_provider_id || ""));
    renderWriterPickChecklist("persona", state.writerSettingPersonaRows || []);
    renderWriterPickChecklist("template", state.writerSettingTemplateRows || []);
  }

  function captureWriterPolicyFromForm() {
    const prev = getCurrentWriterPolicy();
    return {
      persona_ids: [...new Set((state.writerSettingPersonaIds || []).map((v) => Number(v)).filter((v) => Number.isFinite(v)))],
      template_ids: [...new Set((state.writerSettingTemplateIds || []).map((v) => Number(v)).filter((v) => Number.isFinite(v)))],
      persona_cursor: Number(prev.persona_cursor || 0),
      template_cursor: Number(prev.template_cursor || 0),
      default_ai_provider_id: toNullableNumber(qs("#writerSettingAiProviderId").value),
      min_source_count: Number(qs("#writerSettingMinSource").value || 3),
      default_tone: qs("#writerSettingTone").value || "informative",
      default_reader_level: qs("#writerSettingReaderLevel").value || "general",
      default_length: qs("#writerSettingLength").value || "medium",
      creativity_level: Number(qs("#writerSettingCreativity").value || 3),
      factuality_level: Number(qs("#writerSettingFactuality").value || 4),
      seo_keywords: qs("#writerSettingSeoKeywords").value || "",
      auto_enabled: !!qs("#writerSettingAutoEnabled").checked,
      auto_interval_minutes: Number(qs("#writerSettingAutoInterval").value || 1440),
      auto_batch_count: Number(qs("#writerSettingAutoBatch").value || 1),
      auto_retry_count: Number(qs("#writerSettingAutoRetry").value || 1),
      auto_time_window: qs("#writerSettingAutoWindow").value || "00:00-23:59",
    };
  }

  function saveCurrentScopePolicyToState() {
    const scope = writerCurrentScopeFromNode();
    if (!scope) return;
    const key = writerPolicyKeyForScope(scope);
    const next = { ...(state.writerSettingChannelPolicies || {}) };
    next[key] = captureWriterPolicyFromForm();
    state.writerSettingChannelPolicies = next;
  }

  function renderWriterPolicyTabs(channels) {
    const wrap = qs("#writerPolicyTabs");
    if (!wrap) return;
    const rows = (channels || []).filter((c) => !!c.is_enabled);
    const tabs = rows.map((c) => ({ id: `channel:${c.id}`, label: c.display_name }));
    const current = writerCurrentScopeFromNode();
    if (!tabs.length) {
      state.writerSettingPolicyScope = "";
      wrap.innerHTML = "<span class='hint'>등록된 활성 채널이 없습니다.</span>";
      return;
    }
    if (!tabs.some((t) => t.id === current)) {
      state.writerSettingPolicyScope = tabs[0].id;
    }
    wrap.innerHTML = "";
    tabs.forEach((tab) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn ghost writer-policy-tab";
      btn.textContent = tab.label;
      if (tab.id === writerCurrentScopeFromNode()) btn.classList.add("active");
      btn.addEventListener("click", () => {
        saveCurrentScopePolicyToState();
        state.writerSettingPolicyScope = tab.id;
        renderWriterPolicyTabs(channels);
        syncWriterPolicyFormFromScope();
      });
      wrap.appendChild(btn);
    });
    syncWriterPolicyCopyTargets(tabs);
  }

  function syncWriterPolicyCopyTargets(tabs) {
    const sel = qs("#writerPolicyCopyTarget");
    if (!sel) return;
    const items = Array.isArray(tabs) ? tabs : [];
    const current = writerCurrentScopeFromNode();
    const prev = String(sel.value || "");
    sel.innerHTML = "";
    const candidates = items.filter((t) => t.id !== current);
    if (!candidates.length) {
      const o = document.createElement("option");
      o.value = "";
      o.textContent = "복사 대상 없음";
      sel.appendChild(o);
      sel.disabled = true;
      return;
    }
    sel.disabled = false;
    candidates.forEach((t) => {
      const o = document.createElement("option");
      o.value = t.id;
      o.textContent = t.label;
      sel.appendChild(o);
    });
    if (!selectValueIfExists(sel, prev)) sel.value = candidates[0].id;
  }

  function copyWriterPolicyToTargetScope() {
    const sourceScope = writerCurrentScopeFromNode();
    const targetScope = String(qs("#writerPolicyCopyTarget")?.value || "");
    if (!sourceScope || !targetScope || sourceScope === targetScope) {
      throw new Error("정책 복사 대상 채널을 선택하세요.");
    }
    saveCurrentScopePolicyToState();
    const sourcePolicy = mergeWriterPolicy(writerPolicyDefaults(), (state.writerSettingChannelPolicies || {})[sourceScope] || {});
    const next = { ...(state.writerSettingChannelPolicies || {}) };
    next[targetScope] = JSON.parse(JSON.stringify(sourcePolicy));
    state.writerSettingChannelPolicies = next;
  }

  function syncWriterSettingsViewByNode() {
    const showChannelOnly = state.menuNodeId === "writer.channels";
    qs("#writerPolicyPanel")?.classList.toggle("hidden", showChannelOnly);
    qs("#writerChannelManagePanel")?.classList.toggle("hidden", state.menuNodeId !== "writer.channels");
  }

  function renderWriterPickChecklist(kind, rows) {
    const isPersona = kind === "persona";
    const wrap = qs(isPersona ? "#writerSettingPersonaChecklist" : "#writerSettingTemplateChecklist");
    if (!wrap) return;
    wrap.innerHTML = "";
    const ids = new Set((isPersona ? state.writerSettingPersonaIds : state.writerSettingTemplateIds).map((v) => Number(v)));
    const safeRows = (rows || []);
    if (!safeRows.length) {
      wrap.innerHTML = `<div class='check-empty'>등록된 ${isPersona ? "페르소나" : "템플릿"}가 없습니다.</div>`;
    } else {
      safeRows.forEach((row) => {
        const item = document.createElement("label");
        item.className = "check-item";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = ids.has(Number(row.id));
        input.addEventListener("change", () => {
          const sid = Number(row.id);
          const next = new Set((isPersona ? state.writerSettingPersonaIds : state.writerSettingTemplateIds).map((v) => Number(v)));
          if (input.checked) next.add(sid);
          else next.delete(sid);
          if (isPersona) state.writerSettingPersonaIds = [...next];
          else state.writerSettingTemplateIds = [...next];
          renderWriterPickChecklist(kind, safeRows);
        });
        const text = document.createElement("span");
        text.textContent = isPersona ? (row.tone ? `${row.name} (${row.tone})` : row.name) : `${row.name} (${row.template_type}, v${row.version})`;
        item.appendChild(input);
        item.appendChild(text);
        wrap.appendChild(item);
      });
    }
    const selected = safeRows.filter((row) => ids.has(Number(row.id))).length;
    const total = safeRows.length;
    const counter = qs(isPersona ? "#writerPersonaPickCount" : "#writerTemplatePickCount");
    if (counter) counter.textContent = `${selected}/${total}`;
    const all = qs(isPersona ? "#writerPersonaPickAll" : "#writerTemplatePickAll");
    if (all) all.checked = total > 0 && selected === total;
  }

  function toggleWriterPickChecklistAll(kind, checked) {
    const isPersona = kind === "persona";
    const rows = isPersona ? (state.writerSettingPersonaRows || []) : (state.writerSettingTemplateRows || []);
    if (isPersona) {
      state.writerSettingPersonaIds = checked ? rows.map((row) => Number(row.id)) : [];
    } else {
      state.writerSettingTemplateIds = checked ? rows.map((row) => Number(row.id)) : [];
    }
    renderWriterPickChecklist(kind, rows);
  }

  function ensureWriterPolicySelectedItems() {
    if (!Array.isArray(state.writerSettingPersonaIds) || !state.writerSettingPersonaIds.length) {
      throw new Error("사용할 페르소나를 1개 이상 선택하세요.");
    }
    if (!Array.isArray(state.writerSettingTemplateIds) || !state.writerSettingTemplateIds.length) {
      throw new Error("사용할 템플릿을 1개 이상 선택하세요.");
    }
  }

  function validateWriterAutoTimeWindow(value) {
    const text = String(value || "").trim();
    const m = text.match(/^([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)$/);
    if (!m) return false;
    const start = Number(m[1]) * 60 + Number(m[2]);
    const end = Number(m[3]) * 60 + Number(m[4]);
    return start <= end;
  }

  function validateWriterPolicyState(providerRows) {
    const activePersonas = new Set((state.writerSettingPersonaRows || []).filter((r) => !!r.is_active).map((r) => Number(r.id)));
    const activeTemplates = new Set((state.writerSettingTemplateRows || []).filter((r) => !!r.is_active).map((r) => Number(r.id)));
    const activeProviders = new Set((providerRows || []).filter((r) => !!r.is_enabled).map((r) => Number(r.id)));
    const policies = state.writerSettingChannelPolicies || {};
    Object.entries(policies).forEach(([scope, policy]) => {
      const channelId = writerChannelIdFromScope(scope);
      if (!channelId) return;
      const p = mergeWriterPolicy(writerPolicyDefaults(), policy || {});
      if (!Array.isArray(p.persona_ids) || !p.persona_ids.some((id) => activePersonas.has(Number(id)))) {
        throw new Error(`채널 ${channelId}: 활성 페르소나를 1개 이상 선택하세요.`);
      }
      if (!Array.isArray(p.template_ids) || !p.template_ids.some((id) => activeTemplates.has(Number(id)))) {
        throw new Error(`채널 ${channelId}: 활성 템플릿을 1개 이상 선택하세요.`);
      }
      if (p.default_ai_provider_id && !activeProviders.has(Number(p.default_ai_provider_id))) {
        throw new Error(`채널 ${channelId}: 기본 AI가 비활성 상태입니다.`);
      }
      if (!validateWriterAutoTimeWindow(p.auto_time_window)) {
        throw new Error(`채널 ${channelId}: 실행 시간대 형식이 올바르지 않습니다. 예) 09:00-18:00`);
      }
    });
  }

  function getSortedWriterChannels(rows) {
    const list = Array.isArray(rows) ? [...rows] : [];
    const mode = String(state.writerChannelSort || "name_asc");
    if (mode === "status_first") {
      const rank = { auth_error: 0, expiring: 1, paused: 2, active: 3 };
      return list.sort((a, b) => {
        const ra = rank[String(a.status || "active")] ?? 9;
        const rb = rank[String(b.status || "active")] ?? 9;
        if (ra !== rb) return ra - rb;
        return String(a.display_name || a.code || "").localeCompare(String(b.display_name || b.code || ""), "ko");
      });
    }
    if (mode === "enabled_first") {
      return list.sort((a, b) => {
        const e = Number(!!b.is_enabled) - Number(!!a.is_enabled);
        if (e) return e;
        return String(a.display_name || a.code || "").localeCompare(String(b.display_name || b.code || ""), "ko");
      });
    }
    if (mode === "created_desc") {
      return list.sort((a, b) => Number(b.id || 0) - Number(a.id || 0));
    }
    return list.sort((a, b) => String(a.display_name || a.code || "").localeCompare(String(b.display_name || b.code || ""), "ko"));
  }

  function applyWriterAffiliatePreset() {
    const preset = String(qs("#writerAffiliatePreset")?.value || "");
    const textarea = qs("#writerChannelAffiliateText");
    if (!textarea || !preset) return;
    const map = {
      commerce: "이 글에는 제휴 링크가 포함될 수 있으며, 링크를 통해 구매가 발생하면 일정 수수료를 받을 수 있습니다.",
      review: "본 콘텐츠는 제휴 파트너 활동의 일환으로 소정의 수익을 받을 수 있으나, 의견은 작성자의 주관적 판단에 기반합니다.",
      short: "이 글에는 제휴 링크가 포함될 수 있습니다.",
    };
    textarea.value = map[preset] || textarea.value;
    qs("#writerChannelAffiliate").checked = true;
    syncWriterAffiliateTextState();
  }

  async function refreshWriterChannelTable() {
    const rows = await request("/api/writer-channels");
    state.writerChannelRows = Array.isArray(rows) ? rows : [];
    const list = qs("#writerChannelCardList");
    if (!list) return rows;
    list.innerHTML = "";
    const sortedRows = getSortedWriterChannels(state.writerChannelRows);
    if (!sortedRows.length) {
      list.innerHTML = "<div class='writer-channel-card-empty'>작성 채널 없음</div>";
      return rows;
    }

    let selectedExists = false;
    sortedRows.forEach((r) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "writer-channel-card";
      if (state.selectedWriterSettingChannelId === r.id) {
        card.classList.add("selected");
        selectedExists = true;
      }
      const enabledText = r.is_enabled ? "활성" : "비활성";
      card.innerHTML = `
        <div class="writer-channel-card-head">
          <div class="writer-channel-card-title">${escapeHtml(r.display_name || r.code || "-")}</div>
          <span class="badge-status ${r.is_enabled ? "ok" : "neutral"}">${enabledText}</span>
        </div>
        <div class="writer-channel-card-code">${escapeHtml(r.code || "-")}</div>
        <div class="writer-channel-card-meta">
          <span class="badge-channel">${escapeHtml(writerChannelTypeLabel(r.channel_type))}</span>
          <span class="badge-channel">${escapeHtml(writerChannelConnectionLabel(r.connection_type))}</span>
          <span class="badge-status ${writerChannelStatusClass(r.status)}">${escapeHtml(writerChannelStatusLabel(r.status))}</span>
        </div>
      `;
      card.addEventListener("click", () => {
        state.selectedWriterSettingChannelId = r.id;
        qsa(".writer-channel-card").forEach((el) => el.classList.remove("selected"));
        card.classList.add("selected");
        fillWriterChannelForm(r);
      });
      list.appendChild(card);
    });
    if (!selectedExists) resetWriterChannelFormForCreate();
    return rows;
  }

  async function refreshWriterSettingsSection() {
    const [s, personas, templates, providers, channels] = await Promise.all([
      request("/api/v2/settings/writer"),
      request("/api/writer/personas"),
      request("/api/templates"),
      request("/api/ai-providers"),
      request("/api/writer-channels"),
    ]);

    syncWriterSettingsViewByNode();
    if (qs("#writerChannelSort")) qs("#writerChannelSort").value = state.writerChannelSort || "name_asc";

    const channelRows = (channels || []).filter((c) => !!c.is_enabled);
    state.writerSettingPersonaRows = personas || [];
    state.writerSettingTemplateRows = templates || [];
    state.writerSettingProviderRows = providers || [];

    const providerSel = qs("#writerSettingAiProviderId");
    providerSel.innerHTML = "<option value=''>자동 선택</option>";
    (providers || [])
      .filter((p) => !!p.is_enabled)
      .sort((a, b) => Number(a.priority || 999) - Number(b.priority || 999))
      .forEach((p) => {
        const o = document.createElement("option");
        o.value = String(p.id);
        o.textContent = `${p.provider}/${p.model_name} (p${p.priority || 999})`;
        providerSel.appendChild(o);
      });
    selectValueIfExists(providerSel, String(s.default_ai_provider_id || ""));

    qs("#writerSettingAiPriority").value = s.ai_provider_priority || "cost_first";
    qs("#writerSettingMinSeoReview").value = String(s.min_seo_review_score || 60);

    const policyMap = {};
    Object.entries(s.channel_policies || {}).forEach(([key, value]) => {
      if (!value || typeof value !== "object") return;
      policyMap[`channel:${key}`] = mergeWriterPolicy(writerPolicyDefaults(), value);
    });
    state.writerSettingChannelPolicies = policyMap;
    renderWriterPolicyTabs(channelRows);
    syncWriterPolicyFormFromScope();
    await refreshWriterChannelTable();
  }

  async function saveWriterSettingsSection() {
    saveCurrentScopePolicyToState();
    ensureWriterPolicySelectedItems();
    validateWriterPolicyState(state.writerSettingProviderRows || []);
    const policies = state.writerSettingChannelPolicies || {};
    const channelPolicies = {};
    Object.entries(policies).forEach(([key, value]) => {
      if (!key.startsWith("channel:")) return;
      const channelId = Number(key.replace("channel:", ""));
      if (!Number.isFinite(channelId) || channelId <= 0) return;
      channelPolicies[String(channelId)] = mergeWriterPolicy(writerPolicyDefaults(), value);
    });
    await request("/api/v2/settings/writer", {
      method: "POST",
      body: JSON.stringify({
        default_ai_provider_id: toNullableNumber(qs("#writerSettingAiProviderId").value),
        channel_policies: channelPolicies,
        ai_provider_priority: qs("#writerSettingAiPriority").value || "cost_first",
        min_seo_review_score: clampInt(qs("#writerSettingMinSeoReview").value || 60, 0, 100, 60),
      }),
    });
  }

  const publishSettingsModule = window.createPublishSettingsModule({
    qs,
    qsa,
    state,
    request,
    showAlert,
    showConfirm,
    clearFieldErrors,
    applyFieldErrors,
    selectValueIfExists,
    escapeHtml,
    ENUM_LABELS,
  });
  const {
    normalizePublishSettingSnapshot,
    currentPublishSettingFormPayload,
    publishSettingDiffLines,
    refreshPublishSettingDiffHint,
    getSortedPublishSettingRows,
    refreshPublishSettingsSection,
    savePublishSettingsSection,
    savePublishChannelSetting,
    testPublishSettingApiUrl,
    publishModeLabel,
    publishFormatLabel,
    publishStyleLabel,
  } = publishSettingsModule;

  const monitorModule = window.createMonitorModule({
    qs,
    state,
    request,
    showAlert,
    fmt,
    navigateToNode,
    escapeHtml,
    persistMonitorRetryMeta,
    ENUM_LABELS,
  });
  const {
    monitorStatusClass,
    publisherStatusClass,
    publisherStatusLabel,
    publisherModeClass,
    publisherModeLabel,
    publisherChannelLabel,
    monitorTargetNodeByStage,
    monitorStageLabel,
    monitorLevelFromRow,
    monitorLevelClass,
    monitorFailureGroupKey,
    stopMonitorPolling,
    startMonitorPolling,
    retryMonitorRow,
    openMonitorRowDetail,
    monitorRowKey,
    monitorBackoffSeconds,
    monitorRetryEntry,
    renderMonitorRetryQueue,
    refreshMonitorSection,
  } = monitorModule;

  const publisherModule = window.createPublisherModule({
    qs,
    state,
    request,
    fmt,
    escapeHtml,
    csvEscape,
    downloadTextFile,
    selectValueIfExists,
    publisherStatusClass,
    publisherStatusLabel,
    publisherModeClass,
    publisherModeLabel,
    publisherChannelLabel,
  });
  const {
    refreshPublisherSection,
    renderPublisherHistoryFilters,
    renderPublisherJobTable,
    exportPublisherHistoryCsv,
  } = publisherModule;

  async function refreshWriterResultSection() {
    await refreshWriterResultBoard();
  }

  async function refreshWriterRunSection() {
    await refreshWriterRunSummary();
    renderWriterLogDashboard();
  }

  function installImmediateCheckableBridge() {
    const SKIP_KEY = "__instantChangeSkip";
    const isCheckable = (node) => node instanceof HTMLInputElement && (node.type === "checkbox" || node.type === "radio");

    document.addEventListener("input", (e) => {
      const node = e.target;
      if (!isCheckable(node)) return;
      node.dataset[SKIP_KEY] = "1";
      const instantChange = new Event("change", { bubbles: true });
      instantChange.__instant = true;
      node.dispatchEvent(instantChange);
      window.setTimeout(() => {
        if (node.dataset[SKIP_KEY] === "1") delete node.dataset[SKIP_KEY];
      }, 250);
    }, true);

    document.addEventListener("change", (e) => {
      const node = e.target;
      if (!isCheckable(node)) return;
      if (e.__instant) return;
      if (node.dataset[SKIP_KEY] === "1") {
        delete node.dataset[SKIP_KEY];
        e.stopImmediatePropagation();
      }
    }, true);
  }

  function syncThemeToggleIcon(theme) {
    const btn = qs("#themeToggle");
    if (!btn) return;
    const normalized = String(theme || "dark").toLowerCase() === "light" ? "light" : "dark";
    if (normalized === "dark") {
      btn.textContent = "🌙";
      btn.title = "현재 다크모드 (클릭 시 라이트모드)";
      btn.setAttribute("aria-label", "현재 다크모드 (클릭 시 라이트모드)");
    } else {
      btn.textContent = "☀";
      btn.title = "현재 라이트모드 (클릭 시 다크모드)";
      btn.setAttribute("aria-label", "현재 라이트모드 (클릭 시 다크모드)");
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    const initialTheme = getInitialTheme();
    applyTheme(initialTheme);
    syncThemeToggleIcon(initialTheme);
    if (isDesktopEmbed()) document.body.classList.add("embedded-desktop");
    setupNativeSelectProxies();
    installImmediateCheckableBridge();
    qs("#themeToggle")?.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "light";
      const next = current === "light" ? "dark" : "light";
      applyTheme(next);
      syncThemeToggleIcon(next);
    });

    await initV2Menus();
    const mode = setupSectionShell();
    renderV2Menus();
    refreshAutomationStatus().catch(() => {});
    startAutomationPolling();

    if (mode === "dashboard") {
      dashboardReadPrefs();
      dashboardBindControls();
      qs("#dashboardRefreshBtn")?.addEventListener("click", () => refreshDashboardSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#dashboardAutoRefreshEnabled")?.addEventListener("change", () => {
        dashboardApplyControlValues();
        startDashboardPolling();
        refreshDashboardSection().catch(() => {});
      });
      ["#dashboardAutoRefreshSec", "#dashboardWarnCollectFail", "#dashboardWarnWriterUnready", "#dashboardWarnPublishFail", "#dashboardWarnMonitorErrors"]
        .forEach((sel) => qs(sel)?.addEventListener("change", () => {
          dashboardApplyControlValues();
          refreshDashboardSection().catch(() => {});
        }));
      try { await refreshDashboardSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      return;
    }

    if (mode === "keyword") {
      qs("#reloadBtn")?.addEventListener("click", refreshKeywordSection);
      qs("#categorySort")?.addEventListener("change", (e) => {
        state.categorySort = String(e.target.value || "name_asc");
        renderCategoryTable();
        syncCategorySelection();
      });
      qs("#keywordSearchInput")?.addEventListener("input", (e) => {
        state.keywordSearch = String(e.target.value || "");
        state.keywordPage = 1;
        renderKeywordTable();
      });
      qs("#keywordSort")?.addEventListener("change", (e) => {
        state.keywordSort = String(e.target.value || "created_desc");
        state.keywordPage = 1;
        renderKeywordTable();
      });
      qs("#sourceKeywordSelect")?.addEventListener("change", async (e) => {
        state.selectedKeywordId = Number(e.target.value || 0) || null;
        renderKeywordTable();
        await loadRelatedSection();
        await loadKeywordSeoProfile(state.selectedKeywordId, { silent: true });
      });
      qs("#relatedSourceFilter")?.addEventListener("change", async (e) => { state.relatedSourceFilter = String(e.target.value || "all"); await loadRelatedSection(); });
      qs("#keywordCategorySelect")?.addEventListener("change", (e) => {
        state.selectedCategoryId = Number(e.target.value || 0) || null;
        state.keywordPage = 1;
        state.selectedKeywordId = null;
        renderCategoryTable();
        renderKeywordTable();
        syncSourceKeywordSelect();
        loadRelatedSection().catch((err) => showAlert(String(err)));
        loadKeywordSeoProfile(state.selectedKeywordId, { silent: true }).catch((err) => showAlert(String(err)));
      });
      qs("#categoryAddBtn")?.addEventListener("click", () => addCategory().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#categoryRenameBtn")?.addEventListener("click", () => renameCategory().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#categoryDeleteBtn")?.addEventListener("click", () => deleteCategory().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#keywordAddBtn")?.addEventListener("click", () => addKeyword().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#keywordBulkAddBtn")?.addEventListener("click", () => addKeywordBulk().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#keywordBulkToggleBtn")?.addEventListener("click", () => toggleKeywordBatch().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#keywordToggleBtn")?.addEventListener("click", () => toggleKeyword().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#keywordDeleteBtn")?.addEventListener("click", () => deleteKeyword().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#relatedReloadBtn")?.addEventListener("click", () => loadRelatedSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#relatedSyncBtn")?.addEventListener("click", () => syncRelatedKeywords().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#keywordSeoReloadBtn")?.addEventListener("click", () => loadKeywordSeoProfile().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#keywordSeoAnalyzeBtn")?.addEventListener("click", () => analyzeKeywordSeoProfile().catch((e) => showAlert(String(e), "오류", "error")));
      if (qs("#categorySort")) qs("#categorySort").value = state.categorySort || "name_asc";
      if (qs("#keywordSort")) qs("#keywordSort").value = state.keywordSort || "created_desc";
      if (qs("#keywordSearchInput")) qs("#keywordSearchInput").value = state.keywordSearch || "";
      try { await refreshKeywordSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      return;
    }

    if (mode === "collection") {
      loadCollectLogState();
      renderCollectLogDashboard();
      setupCollectionSelectUi();
      if (qs("#collectGuideBtn")) qs("#collectGuideBtn").onclick = () => {
        showAlert("수집 실행 안내\n1) 카테고리 선택\n2) 키워드 선택(연관 제외)\n3) 수집 실행 클릭 후 확인\n4) 하단 로그 대시보드에서 진행/결과 확인");
      };
      if (qs("#collectLogClearBtn")) qs("#collectLogClearBtn").onclick = () => {
        clearCollectLogState();
        renderCollectLogDashboard();
      };
      if (qs("#collectRunBtn")) qs("#collectRunBtn").onclick = () => runCollect().catch((e) => {
        appendCollectLogs([`오류: ${String(e)}`]);
        showAlert(String(e), "오류", "error");
      });
      if (qs("#collectStopBtn")) qs("#collectStopBtn").onclick = () => stopCollect().catch((e) => showAlert(String(e), "오류", "error"));
      try { await refreshCollectionSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      startCollectionPolling();
      return;
    }

    if (mode === "collected_data") {
      bindCollectedUi();
      switchCollectedTab(state.collectedTab || "text");
      try { await refreshCollectedDataSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      return;
    }

    if (mode === "labeling") {
      qs("#labelingRefreshBtn")?.addEventListener("click", () => refreshLabelingSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#runContentLabelingBtn")?.addEventListener("click", () => runLabelingStage("content").catch((e) => showAlert(String(e), "오류", "error")));
      qs("#runImageLabelingBtn")?.addEventListener("click", () => runLabelingStage("image").catch((e) => showAlert(String(e), "오류", "error")));
      qs("#relabelImageLabelingBtn")?.addEventListener("click", () => runLabelingStage("image", { relabelExisting: true }).catch((e) => showAlert(String(e), "오류", "error")));
      qs("#retryFailedLabelingBtn")?.addEventListener("click", () => retryFailedLabelingRun().catch((e) => showAlert(String(e), "오류", "error")));
      try { await refreshLabelingSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      startLabelingPolling();
      return;
    }

    if (mode === "persona") {
      qs("#personaRefreshBtn")?.addEventListener("click", () => refreshPersonaSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#personaSearchInput")?.addEventListener("input", (e) => {
        state.personaSearch = String(e.target.value || "");
        refreshPersonaSection().catch((err) => showAlert(String(err), "오류", "error"));
      });
      qs("#personaActiveFilter")?.addEventListener("change", (e) => {
        state.personaActiveFilter = String(e.target.value || "all");
        refreshPersonaSection().catch((err) => showAlert(String(err), "오류", "error"));
      });
      qs("#personaActive")?.addEventListener("change", () => syncManageSwitchVisuals());
      qs("#personaPreviewBtn")?.addEventListener("click", () => showAlert(personaPreviewText(personaPayload()), "샘플 문체", "info"));
      qs("#personaAddBtn")?.addEventListener("click", () => request("/api/personas", { method: "POST", body: JSON.stringify(personaPayload()) }).then(async () => { showActionAlert("페르소나", "create", true); await refreshPersonaSection(); }).catch((e) => showAlert(String(e), "오류", "error")));
      qs("#personaUpdateBtn")?.addEventListener("click", () => { if (!state.selectedPersonaId) return showAlert("수정할 페르소나를 선택하세요."); request(`/api/personas/${state.selectedPersonaId}/update`, { method: "POST", body: JSON.stringify(personaPayload()) }).then(async () => { showActionAlert("페르소나", "update", true); await refreshPersonaSection(); }).catch((e) => showAlert(String(e), "오류", "error")); });
      qs("#personaDeleteBtn")?.addEventListener("click", () => { if (!state.selectedPersonaId) return showAlert("삭제할 페르소나를 선택하세요."); request(`/api/personas/${state.selectedPersonaId}`, { method: "DELETE" }).then(() => { state.selectedPersonaId = null; showActionAlert("페르소나", "delete", true); return refreshPersonaSection(); }).catch((e) => showAlert(String(e), "오류", "error")); });
      qs("#personaBanned")?.addEventListener("input", () => refreshPersonaCollisionHint().catch(() => {}));
      if (qs("#personaSearchInput")) qs("#personaSearchInput").value = state.personaSearch || "";
      if (qs("#personaActiveFilter")) qs("#personaActiveFilter").value = state.personaActiveFilter || "all";
      syncManageSwitchVisuals();
      try { await refreshPersonaSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      return;
    }

    if (mode === "template") {
      qs("#templateRefreshBtn")?.addEventListener("click", () => refreshTemplateSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#templateActive")?.addEventListener("change", () => syncManageSwitchVisuals());
      qs("#templateDiffBtn")?.addEventListener("click", () => { try { showTemplateDiff(); } catch (e) { showAlert(String(e), "오류", "error"); } });
      qs("#templateCloneBtn")?.addEventListener("click", () => cloneTemplateAsNewVersion().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#templateTestRunBtn")?.addEventListener("click", () => { try { runTemplateTest(); } catch (e) { showAlert(String(e), "오류", "error"); } });
      qs("#templateAddBtn")?.addEventListener("click", () => request("/api/templates", { method: "POST", body: JSON.stringify(templatePayload()) }).then(() => { showActionAlert("템플릿", "create", true); return refreshTemplateSection(); }).catch((e) => showAlert(String(e), "오류", "error")));
      qs("#templateUpdateBtn")?.addEventListener("click", () => { if (!state.selectedTemplateId) return showAlert("수정할 템플릿을 선택하세요."); request(`/api/templates/${state.selectedTemplateId}/update`, { method: "POST", body: JSON.stringify(templatePayload()) }).then(() => { showActionAlert("템플릿", "update", true); return refreshTemplateSection(); }).catch((e) => showAlert(String(e), "오류", "error")); });
      qs("#templateDeleteBtn")?.addEventListener("click", () => { if (!state.selectedTemplateId) return showAlert("삭제할 템플릿을 선택하세요."); request(`/api/templates/${state.selectedTemplateId}`, { method: "DELETE" }).then(() => { state.selectedTemplateId = null; showActionAlert("템플릿", "delete", true); return refreshTemplateSection(); }).catch((e) => showAlert(String(e), "오류", "error")); });
      syncManageSwitchVisuals();
      try { await refreshTemplateSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      return;
    }

    if (mode === "ai_provider") {
      qs("#providerRefreshBtn")?.addEventListener("click", () => refreshProviderSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#providerPaid")?.addEventListener("change", () => syncManageSwitchVisuals());
      qs("#providerEnabled")?.addEventListener("change", () => syncManageSwitchVisuals());
      qs("#providerAlias")?.addEventListener("input", () => refreshProviderAliasHint().catch(() => {}));
      qs("#providerHealthBtn")?.addEventListener("click", () => healthCheckProvider().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#providerNormalizePriorityBtn")?.addEventListener("click", () => normalizeProviderPriorities().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#providerAddBtn")?.addEventListener("click", () => request("/api/ai-providers", { method: "POST", body: JSON.stringify(providerPayload()) }).then(() => { showActionAlert("AI API", "create", true); return refreshProviderSection(); }).catch((e) => showAlert(String(e), "오류", "error")));
      qs("#providerUpdateBtn")?.addEventListener("click", () => { if (!state.selectedProviderId) return showAlert("수정할 항목을 선택하세요."); request(`/api/ai-providers/${state.selectedProviderId}/update`, { method: "POST", body: JSON.stringify(providerPayload()) }).then(() => { showActionAlert("AI API", "update", true); return refreshProviderSection(); }).catch((e) => showAlert(String(e), "오류", "error")); });
      qs("#providerDeleteBtn")?.addEventListener("click", () => { if (!state.selectedProviderId) return showAlert("삭제할 항목을 선택하세요."); request(`/api/ai-providers/${state.selectedProviderId}`, { method: "DELETE" }).then(() => { state.selectedProviderId = null; showActionAlert("AI API", "delete", true); return refreshProviderSection(); }).catch((e) => showAlert(String(e), "오류", "error")); });
      syncManageSwitchVisuals();
      try { await refreshProviderSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      return;
    }


    if (mode === "writer_run") {
      loadWriterLogState();
      renderWriterLogDashboard();
      refreshWriterRunChannelMetricHint();
      qs("#writerRefreshBtn")?.addEventListener("click", () => refreshWriterRunSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#writerGuideBtn")?.addEventListener("click", () => {
        showAlert("글 작성 실행 안내\n1) 글 작성 설정에서 채널별 정책 저장\n2) 실행 화면에서 저장된 정책 요약 확인\n3) 글 작성 실행 클릭\n4) 하단 실행 로그 대시보드에서 진행/결과 확인");
      });
      qs("#writerRunBtn")?.addEventListener("click", () => runWriter().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#writerStopBtn")?.addEventListener("click", () => stopWriter().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#writerResumeBtn")?.addEventListener("click", () => runWriter().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#writerLogClearBtn")?.addEventListener("click", () => clearWriterLogState());
      qs("#writerLogDownloadTxtBtn")?.addEventListener("click", () => downloadWriterLogsTxt());
      qs("#writerLogDownloadCsvBtn")?.addEventListener("click", () => downloadWriterLogsCsv());
      try { await refreshWriterRunSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      startWriterPolling();
      return;
    }

    if (mode === "writer_result") {
      qs("#writerResultRefreshBtn")?.addEventListener("click", () => refreshWriterResultSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#writerBoardPickAll")?.addEventListener("change", (e) => {
        const checked = !!e.target.checked;
        const rows = getFilteredWriterBoardRows();
        const totalPages = Math.max(1, Math.ceil(rows.length / state.writerBoardPageSize));
        state.writerBoardPage = Math.min(Math.max(1, state.writerBoardPage), totalPages);
        const start = (state.writerBoardPage - 1) * state.writerBoardPageSize;
        const pageRows = rows.slice(start, start + state.writerBoardPageSize);
        const ids = new Set(getSelectedWriterBoardIds());
        pageRows.forEach((r) => {
          const id = Number(r.id || 0);
          if (!id) return;
          if (checked) ids.add(id);
          else ids.delete(id);
        });
        setWriterBoardSelectedIds([...ids]);
        renderWriterBoardTable();
      });
      qs("#writerBoardBulkPublishBtn")?.addEventListener("click", () => bulkPublishWriterBoardArticles().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#writerBoardBulkStatusBtn")?.addEventListener("click", () => bulkUpdateWriterBoardStatus().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#writerArticleSaveBtn")?.addEventListener("click", () => saveWriterArticleEditor().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#writerArticleRegenerateBtn")?.addEventListener("click", () => regenerateWriterArticle(state.writerEditingArticleId).catch((e) => showAlert(String(e), "오류", "error")));
      qs("#writerArticleCloseBtn")?.addEventListener("click", () => closeWriterArticleEditor());
      qs("#writerArticleCloseX")?.addEventListener("click", () => closeWriterArticleEditor());
      qs("#writerArticleBackdrop")?.addEventListener("click", () => closeWriterArticleEditor());
      qs("#writerArticleViewCloseBtn")?.addEventListener("click", () => closeWriterArticleViewer());
      qs("#writerArticleViewCloseX")?.addEventListener("click", () => closeWriterArticleViewer());
      qs("#writerArticleViewBackdrop")?.addEventListener("click", () => closeWriterArticleViewer());
      qs("#writerBoardSearch")?.addEventListener("input", (e) => {
        state.writerBoardSearch = String(e.target.value || "");
        state.writerBoardPage = 1;
        renderWriterBoardTable();
      });
      qs("#writerBoardStatusFilter")?.addEventListener("change", (e) => {
        state.writerBoardStatusFilter = String(e.target.value || "all");
        state.writerBoardPage = 1;
        renderWriterBoardTable();
      });
      qs("#writerBoardFilterResetBtn")?.addEventListener("click", () => {
        state.writerBoardSearch = "";
        state.writerBoardStatusFilter = "all";
        state.writerBoardPage = 1;
        setWriterBoardSelectedIds([]);
        if (qs("#writerBoardSearch")) qs("#writerBoardSearch").value = "";
        if (qs("#writerBoardStatusFilter")) qs("#writerBoardStatusFilter").value = "all";
        renderWriterBoardTable();
      });
      try { await refreshWriterResultSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      return;
    }

    if (mode === "publisher") {
      if (qs("#publisherHistoryFrom")) qs("#publisherHistoryFrom").value = state.publisherHistoryFrom || "";
      if (qs("#publisherHistoryTo")) qs("#publisherHistoryTo").value = state.publisherHistoryTo || "";
      qs("#publisherRefreshBtn")?.addEventListener("click", () => refreshPublisherSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#publisherHistoryFrom")?.addEventListener("change", (e) => {
        state.publisherHistoryFrom = String(e.target.value || "");
        state.publisherJobPage = 1;
        renderPublisherJobTable();
      });
      qs("#publisherHistoryTo")?.addEventListener("change", (e) => {
        state.publisherHistoryTo = String(e.target.value || "");
        state.publisherJobPage = 1;
        renderPublisherJobTable();
      });
      qs("#publisherHistoryStatusFilter")?.addEventListener("change", (e) => {
        state.publisherHistoryStatusFilter = String(e.target.value || "all");
        state.publisherJobPage = 1;
        renderPublisherJobTable();
      });
      qs("#publisherHistoryChannelFilter")?.addEventListener("change", (e) => {
        state.publisherHistoryChannelFilter = String(e.target.value || "all");
        state.publisherJobPage = 1;
        renderPublisherJobTable();
      });
      qs("#publisherHistorySearch")?.addEventListener("input", (e) => {
        state.publisherHistorySearch = String(e.target.value || "");
        state.publisherJobPage = 1;
        renderPublisherJobTable();
      });
      qs("#publisherHistoryResetBtn")?.addEventListener("click", () => {
        state.publisherHistoryFrom = "";
        state.publisherHistoryTo = "";
        state.publisherHistoryStatusFilter = "all";
        state.publisherHistoryChannelFilter = "all";
        state.publisherHistorySearch = "";
        state.publisherJobPage = 1;
        if (qs("#publisherHistoryFrom")) qs("#publisherHistoryFrom").value = "";
        if (qs("#publisherHistoryTo")) qs("#publisherHistoryTo").value = "";
        if (qs("#publisherHistoryStatusFilter")) qs("#publisherHistoryStatusFilter").value = "all";
        if (qs("#publisherHistorySearch")) qs("#publisherHistorySearch").value = "";
        renderPublisherHistoryFilters();
        renderPublisherJobTable();
      });
      qs("#publisherHistoryExportCsvBtn")?.addEventListener("click", () => exportPublisherHistoryCsv());
      qs("#publishAutoPauseBtn")?.addEventListener("click", async () => {
        try {
          const pauseUntil = String(qs("#publishAutoPauseUntil")?.value || "");
          if (!pauseUntil) throw new Error("일시중지 시각을 선택하세요.");
          await request("/api/publish/auto/pause-until", { method: "POST", body: JSON.stringify({ pause_until: pauseUntil }) });
          await refreshPublisherSection();
        } catch (e) { showAlert(String(e), "오류", "error"); }
      });
      qs("#publishAutoResumeBtn")?.addEventListener("click", async () => {
        try {
          await request("/api/publish/auto/pause-until", { method: "POST", body: JSON.stringify({ pause_until: "" }) });
          await refreshPublisherSection();
        } catch (e) { showAlert(String(e), "오류", "error"); }
      });
      qs("#publishAutoStartBtn")?.addEventListener("click", async () => {
        try {
          await request("/api/publish/auto/start", { method: "POST", body: "{}" });
          await refreshPublisherSection();
        } catch (e) { showAlert(String(e), "오류", "error"); }
      });
      qs("#publishAutoStopBtn")?.addEventListener("click", async () => {
        try {
          await request("/api/publish/auto/stop", { method: "POST", body: "{}" });
          await refreshPublisherSection();
        } catch (e) { showAlert(String(e), "오류", "error"); }
      });
      qs("#publishAutoTickBtn")?.addEventListener("click", async () => {
        try {
          const result = await request("/api/publish/auto/tick", { method: "POST", body: "{}" });
          if (typeof result.processed === "number") {
            showAlert(`즉시 실행 완료: ${result.processed}건 처리`, "완료", "success");
          }
          await refreshPublisherSection();
        } catch (e) { showAlert(String(e), "오류", "error"); }
      });
      try { await refreshPublisherSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      return;
    }
    if (mode === "collect_settings") {
      qs("#collectSettingSaveBtn")?.addEventListener("click", () => saveCollectSettingsSection().then(() => showAlert("설정이 저장되었습니다.", "성공", "success")).catch((e) => showAlert(String(e), "오류", "error")));
      qs("#collectChannelSearch")?.addEventListener("input", (e) => {
        state.collectSettingChannelSearch = String(e.target.value || "");
        renderCollectChecklist("channel");
      });
      qs("#collectCategorySearch")?.addEventListener("input", (e) => {
        state.collectSettingCategorySearch = String(e.target.value || "");
        renderCollectChecklist("category");
      });
      ["#collectSettingInterval", "#collectSettingMaxResults", "#collectSettingTimeout", "#collectSettingRetry", "#collectSettingAutoRelatedSync"]
        .forEach((sel) => qs(sel)?.addEventListener("change", () => refreshCollectSettingHints()));
      qsa("input[name='collectSettingScope']").forEach((node) => node.addEventListener("change", () => refreshCollectSettingHints()));
      qs("#collectSettingResetBtn")?.addEventListener("click", () => {
        setCollectScopeValue("selected");
        qs("#collectSettingInterval").value = 60;
        qs("#collectSettingMaxResults").value = 3;
        qs("#collectSettingTimeout").value = 15;
        qs("#collectSettingRetry").value = 1;
        qs("#collectSettingAutoRelatedSync").checked = false;
        state.collectSettingKeywordSourceCodes = ["google_suggest", "naver"];
        state.collectSettingChannelCodes = [];
        state.collectSettingCategoryIds = [];
        renderKeywordSourceChecklist();
        renderCollectChecklist("channel");
        renderCollectChecklist("category");
        refreshCollectSettingHints();
      });
      qs("#collectChannelAll")?.addEventListener("change", (e) => toggleCollectChecklistAll("channel", !!e.target.checked));
      qs("#collectCategoryAll")?.addEventListener("change", (e) => toggleCollectChecklistAll("category", !!e.target.checked));
      if (qs("#collectChannelSearch")) qs("#collectChannelSearch").value = state.collectSettingChannelSearch || "";
      if (qs("#collectCategorySearch")) qs("#collectCategorySearch").value = state.collectSettingCategorySearch || "";
      try { await refreshCollectSettingsSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      return;
    }

    if (mode === "label_settings") {
      qs("#labelSettingSaveBtn")?.addEventListener("click", () => saveLabelSettingsSection().then(() => showAlert("설정이 저장되었습니다.", "성공", "success")).catch((e) => showAlert(String(e), "오류", "error")));
      qs("#labelSettingTickBtn")?.addEventListener("click", () => tickAutoLabeling().then(() => showAlert("자동 라벨링 1회 실행을 완료했습니다.", "완료", "success")).catch((e) => showAlert(String(e), "오류", "error")));
      qs("#labelSettingAutoEnabled")?.addEventListener("change", () => {
        saveLabelSettingsSection().catch((e) => showAlert(String(e), "오류", "error"));
      });
      qs("#labelSettingPresetApplyBtn")?.addEventListener("click", async () => {
        const presetName = String(qs("#labelSettingPreset")?.value || "default");
        applyLabelSettingToForm(labelingPresetValues(presetName));
        await refreshLabelSettingHints();
      });
      ["#labelSettingMethod", "#labelSettingBatch", "#labelSettingQuality", "#labelSettingPolicy", "#labelSettingInterval", "#labelSettingFreeLimit", "#labelSettingPaidLimit", "#labelSettingThresholdMid", "#labelSettingThresholdHigh"]
        .forEach((sel) => qs(sel)?.addEventListener("change", () => {
          syncLabelSettingModeUi();
          refreshLabelSettingHints().catch(() => {});
        }));
      try { await refreshLabelSettingsSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      return;
    }

    if (mode === "writer_settings") {
      qs("#writerSettingSaveBtn")?.addEventListener("click", () => saveWriterSettingsSection().then(() => showAlert("설정이 저장되었습니다.", "성공", "success")).catch((e) => showAlert(String(e), "오류", "error")));
      qs("#writerPolicyCopyBtn")?.addEventListener("click", () => {
        try {
          copyWriterPolicyToTargetScope();
          showAlert("현재 채널 정책을 대상 채널에 복사했습니다.", "성공", "success");
        } catch (e) {
          showAlert(String(e), "오류", "error");
        }
      });
      qs("#writerPersonaPickAll")?.addEventListener("change", (e) => toggleWriterPickChecklistAll("persona", !!e.target.checked));
      qs("#writerTemplatePickAll")?.addEventListener("change", (e) => toggleWriterPickChecklistAll("template", !!e.target.checked));
      qs("#writerChannelEnabled")?.addEventListener("change", () => syncWriterChannelSwitches());
      qs("#writerChannelAffiliate")?.addEventListener("change", () => syncWriterAffiliateTextState());
      qs("#writerChannelSort")?.addEventListener("change", (e) => {
        state.writerChannelSort = String(e.target.value || "name_asc");
        refreshWriterChannelTable().catch((err) => showAlert(String(err), "오류", "error"));
      });
      qs("#writerAffiliatePresetApplyBtn")?.addEventListener("click", () => applyWriterAffiliatePreset());
      ["#writerChannelLoginId", "#writerChannelPassword", "#writerChannelApiKey"]
        .forEach((sel) => qs(sel)?.addEventListener("input", () => syncWriterAuthChangeHint()));
      qs("#writerChannelRefreshBtn")?.addEventListener("click", () => refreshWriterChannelTable().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#writerChannelAddBtn")?.addEventListener("click", () => {
        const fieldMap = {
          code: "#writerChannelCode",
          display_name: "#writerChannelName",
          channel_type: "#writerChannelType",
          connection_type: "#writerChannelConnection",
          status: "#writerChannelStatus",
          auth_type: "#writerChannelAuthType",
          api_endpoint_url: "#writerChannelApiUrl",
          notes: "#writerChannelAffiliateText",
        };
        clearFieldErrors(Object.values(fieldMap));
        applyFieldErrors({}, fieldMap, "#writerChannelValidationHint");
        const payload = writerChannelPayload();
        validateWriterChannelPayload(payload);
        return request("/api/writer-channels", { method: "POST", body: JSON.stringify(payload) })
          .then(() => {
            showAlert("작성 채널이 추가되었습니다.", "성공", "success");
            resetWriterChannelFormForCreate();
            return refreshWriterSettingsSection();
          })
          .catch((e) => {
            applyFieldErrors(e?.fields, fieldMap, "#writerChannelValidationHint");
            showAlert(String(e), "오류", "error");
          });
      });
      qs("#writerChannelUpdateBtn")?.addEventListener("click", () => {
        if (!state.selectedWriterSettingChannelId) return showAlert("수정할 작성 채널을 선택하세요.");
        const fieldMap = {
          code: "#writerChannelCode",
          display_name: "#writerChannelName",
          channel_type: "#writerChannelType",
          connection_type: "#writerChannelConnection",
          status: "#writerChannelStatus",
          auth_type: "#writerChannelAuthType",
          api_endpoint_url: "#writerChannelApiUrl",
          notes: "#writerChannelAffiliateText",
        };
        clearFieldErrors(Object.values(fieldMap));
        applyFieldErrors({}, fieldMap, "#writerChannelValidationHint");
        const payload = writerChannelPayload();
        validateWriterChannelPayload(payload);
        return request(`/api/writer-channels/${state.selectedWriterSettingChannelId}/update`, { method: "POST", body: JSON.stringify(payload) })
          .then(() => {
            showAlert("작성 채널이 수정되었습니다.", "성공", "success");
            return refreshWriterSettingsSection();
          })
          .catch((e) => {
            applyFieldErrors(e?.fields, fieldMap, "#writerChannelValidationHint");
            showAlert(String(e), "오류", "error");
          });
      });
      qs("#writerChannelToggleBtn")?.addEventListener("click", () => {
        if (!state.selectedWriterSettingChannelId) return showAlert("활성/비활성할 작성 채널을 선택하세요.");
        return request(`/api/writer-channels/${state.selectedWriterSettingChannelId}/toggle`, { method: "POST", body: "{}" })
          .then(() => {
            showAlert("작성 채널 상태가 변경되었습니다.", "성공", "success");
            return refreshWriterSettingsSection();
          })
          .catch((e) => showAlert(String(e), "오류", "error"));
      });
      qs("#writerChannelDeleteBtn")?.addEventListener("click", () => {
        if (!state.selectedWriterSettingChannelId) return showAlert("삭제할 작성 채널을 선택하세요.");
        return request(`/api/writer-channels/${state.selectedWriterSettingChannelId}`, { method: "DELETE" })
          .then(() => {
            state.selectedWriterSettingChannelId = null;
            resetWriterChannelFormForCreate();
            showAlert("작성 채널이 삭제되었습니다.", "성공", "success");
            return refreshWriterSettingsSection();
          })
          .catch((e) => showAlert(String(e), "오류", "error"));
      });
      syncWriterChannelCodePolicy();
      syncWriterAuthChangeHint();
      syncWriterAffiliateTextState();
      syncWriterChannelSwitches();
      try { await refreshWriterSettingsSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      return;
    }

    if (mode === "publish_settings") {
      qs("#publishSettingSaveBtnV2")?.addEventListener("click", () => savePublishSettingsSection().then(() => showAlert("설정이 저장되었습니다.", "성공", "success")).catch((e) => showAlert(String(e), "오류", "error")));
      qs("#publishSettingSearch")?.addEventListener("input", (e) => {
        state.publishSettingSearch = String(e.target.value || "");
        refreshPublishSettingsSection().catch((err) => showAlert(String(err), "오류", "error"));
      });
      qs("#publishSettingSort")?.addEventListener("change", (e) => {
        state.publishSettingSort = String(e.target.value || "name_asc");
        refreshPublishSettingsSection().catch((err) => showAlert(String(err), "오류", "error"));
      });
      qs("#publishSettingRefreshBtn")?.addEventListener("click", () => refreshPublishSettingsSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#publishSettingSaveBtn")?.addEventListener("click", () => savePublishChannelSetting().then(() => { showAlert("채널 설정이 저장되었습니다.", "성공", "success"); return refreshPublishSettingsSection(); }).catch((e) => showAlert(String(e), "오류", "error")));
      qs("#publishSettingTestApiBtn")?.addEventListener("click", () => testPublishSettingApiUrl().catch((e) => showAlert(String(e), "오류", "error")));
      ["#publishSettingChannel", "#publishSettingApi", "#publishSettingCycle", "#publishSettingMode", "#publishSettingFormat", "#publishSettingStyle"]
        .forEach((sel) => qs(sel)?.addEventListener("change", () => refreshPublishSettingDiffHint()));
      qs("#publishChannelToggleBtn")?.addEventListener("click", () => {
        const selectedCode = String(qs("#publishSettingChannel")?.value || "");
        const resolveId = state.selectedPublishChannelId;
        if (!resolveId && !selectedCode) return showAlert("활성/비활성할 채널을 먼저 선택하세요.");
        return request("/api/publish-channels")
          .then((rows) => {
            const list = Array.isArray(rows) ? rows : [];
            const row = resolveId ? list.find((r) => Number(r.id) === Number(resolveId)) : list.find((r) => String(r.code || "") === selectedCode);
            if (!row || !row.id) throw new Error("채널 정보를 찾을 수 없습니다.");
            return request(`/api/publish-channels/${row.id}/toggle`, { method: "POST", body: "{}" });
          })
          .then(() => refreshPublishSettingsSection())
          .catch((e) => showAlert(String(e), "오류", "error"));
      });
      if (qs("#publishSettingSearch")) qs("#publishSettingSearch").value = state.publishSettingSearch || "";
      if (qs("#publishSettingSort")) qs("#publishSettingSort").value = state.publishSettingSort || "name_asc";
      try { await refreshPublishSettingsSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      return;
    }

    if (mode === "monitor") {
      loadMonitorRetryMeta();
      if (qs("#monitorLevelFilter")) qs("#monitorLevelFilter").value = state.monitorLevelFilter || "all";
      if (qs("#monitorStreamEnabled")) qs("#monitorStreamEnabled").checked = !!state.monitorStreamEnabled;
      if (qs("#monitorPollSec")) qs("#monitorPollSec").value = String(state.monitorPollSec || 5);
      if (qs("#monitorRetryMax")) qs("#monitorRetryMax").value = String(state.monitorRetryMax || 5);
      qs("#monitorRefreshBtn")?.addEventListener("click", () => refreshMonitorSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#monitorPrevPageBtn")?.addEventListener("click", () => {
        const prev = state.monitorCursorStack.pop() || "";
        state.monitorCursor = prev;
        refreshMonitorSection().catch((e) => showAlert(String(e), "오류", "error"));
      });
      qs("#monitorNextPageBtn")?.addEventListener("click", () => {
        if (!state.monitorNextCursor) return;
        state.monitorCursorStack.push(state.monitorCursor || "");
        state.monitorCursor = state.monitorNextCursor;
        refreshMonitorSection().catch((e) => showAlert(String(e), "오류", "error"));
      });
      qs("#monitorResetCursorBtn")?.addEventListener("click", () => {
        state.monitorCursor = "";
        state.monitorNextCursor = "";
        state.monitorCursorStack = [];
        refreshMonitorSection().catch((e) => showAlert(String(e), "오류", "error"));
      });
      qs("#monitorStageFilter")?.addEventListener("change", () => refreshMonitorSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#monitorLevelFilter")?.addEventListener("change", () => refreshMonitorSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#monitorTextFilter")?.addEventListener("input", () => refreshMonitorSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#monitorStreamEnabled")?.addEventListener("change", () => refreshMonitorSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#monitorPollSec")?.addEventListener("change", () => refreshMonitorSection().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#monitorRetryMax")?.addEventListener("change", (e) => {
        state.monitorRetryMax = Math.max(1, Math.min(20, Number(e.target.value || 5)));
        renderMonitorRetryQueue(state.monitorLastRows || []);
      });
      qs("#monitorRetryResetBtn")?.addEventListener("click", () => {
        state.monitorRetryMeta = {};
        persistMonitorRetryMeta();
        renderMonitorRetryQueue(state.monitorLastRows || []);
      });
      try { await refreshMonitorSection(); } catch (err) { showAlert(`초기 로딩 실패: ${String(err)}`, "오류", "error"); }
      return;
    }

    if (mode === "settings") {
      return;
    }
  });
})();






















































