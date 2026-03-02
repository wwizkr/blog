(() => {
  function createPublisherModule(ctx) {
    const {
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
    } = ctx || {};

    async function refreshPublisherSection() {
      const [autoStatusRaw, jobsRaw] = await Promise.all([
        request("/api/publish/auto/status"),
        request("/api/publisher/jobs"),
      ]);
      const autoStatus = autoStatusRaw && typeof autoStatusRaw === "object" ? autoStatusRaw : {};
      const jobs = Array.isArray(jobsRaw) ? jobsRaw : [];
      if (qs("#publishAutoEnabled")) qs("#publishAutoEnabled").textContent = autoStatus.enabled ? "실행중" : "중지";
      if (qs("#publishAutoWorker")) qs("#publishAutoWorker").textContent = autoStatus.worker_started ? "동작중" : "미시작";
      if (qs("#publishAutoChannelCount")) qs("#publishAutoChannelCount").textContent = String(autoStatus.auto_channel_count || 0);
      if (qs("#publishAutoLastProcessed")) qs("#publishAutoLastProcessed").textContent = String(autoStatus.last_tick_processed || 0);
      if (qs("#publishAutoLastTickHint")) qs("#publishAutoLastTickHint").textContent = `최근 실행: ${fmt(autoStatus.last_tick_at)}`;
      const nextBody = qs("#publishAutoNextRunTable tbody");
      if (nextBody) {
        const nextRows = Array.isArray(autoStatus.channels) ? autoStatus.channels : [];
        nextBody.innerHTML = nextRows.length ? "" : "<tr><td colspan='3'>자동 채널 없음</td></tr>";
        nextRows.forEach((row) => {
          const tr = document.createElement("tr");
          tr.innerHTML = `<td>${escapeHtml(row.channel_code || "-")}</td><td>${Number(row.cycle_minutes || 60)}</td><td>${fmt(row.next_run_at)}</td>`;
          nextBody.appendChild(tr);
        });
      }

      const logRows = Array.isArray(autoStatus.logs) ? autoStatus.logs : [];
      const logBody = qs("#publishAutoLogTable tbody");
      if (logBody) {
        logBody.innerHTML = logRows.length ? "" : "<tr><td>로그 없음</td></tr>";
        logRows.forEach((line) => {
          const tr = document.createElement("tr");
          tr.innerHTML = `<td>${line || ""}</td>`;
          logBody.appendChild(tr);
        });
      }

      state.publisherJobRows = jobs;
      renderPublisherHistoryFilters();
      renderPublisherJobTable();
    }

    function renderPublisherHistoryFilters() {
      const rows = Array.isArray(state.publisherJobRows) ? state.publisherJobRows : [];
      const channels = Array.from(new Set(rows.map((r) => String(r.target_channel || "")).filter(Boolean))).sort();
      const channelSel = qs("#publisherHistoryChannelFilter");
      if (channelSel) {
        const prev = String(state.publisherHistoryChannelFilter || "all");
        channelSel.innerHTML = "";
        const allOpt = document.createElement("option");
        allOpt.value = "all";
        allOpt.textContent = "전체 채널";
        channelSel.appendChild(allOpt);
        channels.forEach((channel) => {
          const o = document.createElement("option");
          o.value = channel;
          o.textContent = channel;
          channelSel.appendChild(o);
        });
        if (!selectValueIfExists(channelSel, prev)) channelSel.value = "all";
        state.publisherHistoryChannelFilter = channelSel.value || "all";
      }
    }

    function renderPublisherJobPager(totalCount, totalPages) {
      const wrap = qs("#publisherJobPager");
      if (!wrap) return;
      wrap.innerHTML = "";
      const info = document.createElement("span");
      info.className = "pager-info";
      info.textContent = `총 ${totalCount}건 / ${state.publisherJobPage} / ${totalPages}`;
      wrap.appendChild(info);
      const prevBtn = document.createElement("button");
      prevBtn.className = "btn ghost";
      prevBtn.textContent = "이전";
      prevBtn.disabled = state.publisherJobPage <= 1;
      prevBtn.addEventListener("click", () => {
        if (state.publisherJobPage <= 1) return;
        state.publisherJobPage -= 1;
        renderPublisherJobTable();
      });
      const nextBtn = document.createElement("button");
      nextBtn.className = "btn ghost";
      nextBtn.textContent = "다음";
      nextBtn.disabled = state.publisherJobPage >= totalPages;
      nextBtn.addEventListener("click", () => {
        if (state.publisherJobPage >= totalPages) return;
        state.publisherJobPage += 1;
        renderPublisherJobTable();
      });
      wrap.appendChild(prevBtn);
      wrap.appendChild(nextBtn);
    }

    function classifyPublishFailCode(message) {
      const text = String(message || "").toLowerCase();
      if (!text) return "";
      if (text.includes("timeout") || text.includes("dns") || text.includes("network")) return "NETWORK";
      if (text.includes("401") || text.includes("403") || text.includes("auth") || text.includes("token")) return "AUTH";
      if (text.includes("format") || text.includes("schema") || text.includes("invalid")) return "FORMAT";
      if (text.includes("429") || text.includes("rate") || text.includes("limit")) return "RATE_LIMIT";
      if (text.includes("retry")) return "RETRY";
      return "";
    }

    function renderPublisherJobTable() {
      const jt = qs("#publisherJobTable tbody");
      if (!jt) return;
      const rows = Array.isArray(state.publisherJobRows) ? state.publisherJobRows : [];
      const statusFilter = String(state.publisherHistoryStatusFilter || "all");
      const channelFilter = String(state.publisherHistoryChannelFilter || "all");
      const textFilter = String(state.publisherHistorySearch || "").trim().toLowerCase();
      const from = String(state.publisherHistoryFrom || "");
      const to = String(state.publisherHistoryTo || "");
      let filtered = rows.filter((r) => {
        if (statusFilter !== "all" && String(r.status || "") !== statusFilter) return false;
        if (channelFilter !== "all" && String(r.target_channel || "") !== channelFilter) return false;
        const createdDate = String((r.created_at || "").slice(0, 10));
        if (from && createdDate && createdDate < from) return false;
        if (to && createdDate && createdDate > to) return false;
        if (textFilter) {
          const haystack = `${r.article_id || ""} ${r.message || ""} ${r.target_channel || ""}`.toLowerCase();
          if (!haystack.includes(textFilter)) return false;
        }
        return true;
      });
      const totalCount = filtered.length;
      const totalPages = Math.max(1, Math.ceil(totalCount / state.publisherJobPageSize));
      if (state.publisherJobPage > totalPages) state.publisherJobPage = totalPages;
      if (state.publisherJobPage < 1) state.publisherJobPage = 1;
      const start = (state.publisherJobPage - 1) * state.publisherJobPageSize;
      filtered = filtered.slice(start, start + state.publisherJobPageSize);
      jt.innerHTML = filtered.length ? "" : "<tr><td colspan='7'>작업 없음</td></tr>";
      filtered.forEach((j) => {
        const tr = document.createElement("tr");
        const statusClass = publisherStatusClass(j.status);
        const statusLabel = publisherStatusLabel(j.status);
        const failCode = classifyPublishFailCode(j.message || "");
        const modeClass = publisherModeClass(j.mode);
        const modeLabel = publisherModeLabel(j.mode);
        const channelLabel = publisherChannelLabel(j.target_channel);
        const statusView = failCode ? `${statusLabel}(${failCode})` : statusLabel;
        tr.innerHTML = `<td>${j.id}</td><td>${j.article_id}</td><td><span class="badge-channel">${channelLabel}</span></td><td><span class="badge-mode ${modeClass}">${modeLabel}</span></td><td><span class="badge-status ${statusClass}">${statusView}</span></td><td>${j.message || ""}</td><td>${fmt(j.created_at)}</td>`;
        jt.appendChild(tr);
      });
      renderPublisherJobPager(totalCount, totalPages);
    }

    function exportPublisherHistoryCsv() {
      const rows = Array.isArray(state.publisherJobRows) ? state.publisherJobRows : [];
      const statusFilter = String(state.publisherHistoryStatusFilter || "all");
      const channelFilter = String(state.publisherHistoryChannelFilter || "all");
      const textFilter = String(state.publisherHistorySearch || "").trim().toLowerCase();
      const from = String(state.publisherHistoryFrom || "");
      const to = String(state.publisherHistoryTo || "");
      const filtered = rows.filter((r) => {
        if (statusFilter !== "all" && String(r.status || "") !== statusFilter) return false;
        if (channelFilter !== "all" && String(r.target_channel || "") !== channelFilter) return false;
        const createdDate = String((r.created_at || "").slice(0, 10));
        if (from && createdDate && createdDate < from) return false;
        if (to && createdDate && createdDate > to) return false;
        if (textFilter) {
          const hay = `${r.article_id || ""} ${r.message || ""} ${r.target_channel || ""}`.toLowerCase();
          if (!hay.includes(textFilter)) return false;
        }
        return true;
      });
      const head = ["id", "article_id", "target_channel", "mode", "status", "fail_code", "message", "created_at"];
      const lines = [head.join(",")];
      filtered.forEach((r) => {
        lines.push([
          csvEscape(r.id),
          csvEscape(r.article_id),
          csvEscape(r.target_channel),
          csvEscape(r.mode),
          csvEscape(r.status),
          csvEscape(classifyPublishFailCode(r.message || "")),
          csvEscape(r.message || ""),
          csvEscape(r.created_at || ""),
        ].join(","));
      });
      downloadTextFile(`publish-history-${new Date().toISOString().slice(0, 10)}.csv`, `${lines.join("\n")}\n`, "text/csv;charset=utf-8");
    }

    return {
      refreshPublisherSection,
      renderPublisherHistoryFilters,
      renderPublisherJobTable,
      exportPublisherHistoryCsv,
    };
  }

  window.createPublisherModule = createPublisherModule;
})();
