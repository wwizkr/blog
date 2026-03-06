(() => {
  function createMonitorModule(ctx) {
    const {
      qs,
      state,
      request,
      showAlert,
      fmt,
      navigateToNode,
      escapeHtml,
      persistMonitorRetryMeta,
      ENUM_LABELS,
    } = ctx || {};

    function monitorStatusClass(status) {
      const s = String(status || "").toLowerCase();
      if (s.includes("fail") || s.includes("error")) return "fail";
      if (s.includes("queued") || s.includes("pending") || s.includes("retry")) return "warn";
      if (s.includes("done") || s.includes("success") || s.includes("ok") || s.includes("completed")) return "ok";
      return "neutral";
    }

    function publisherStatusClass(status) {
      const s = String(status || "").toLowerCase();
      if (s === "done") return "ok";
      if (s === "failed") return "fail";
      if (s === "queued" || s === "processing") return "warn";
      return "neutral";
    }

    function publisherStatusLabel(status) {
      const s = String(status || "").toLowerCase();
      if (s === "done") return "성공";
      if (s === "failed") return "실패";
      if (s === "queued") return "대기";
      if (s === "processing") return "처리중";
      return status || "-";
    }

    function publisherModeClass(mode) {
      const m = String(mode || "").toLowerCase();
      if (m === "auto") return "ok";
      if (m === "semi_auto") return "neutral";
      return "warn";
    }

    function publisherModeLabel(mode) {
      const m = String(mode || "").toLowerCase();
      if (m === "auto") return "자동";
      if (m === "semi_auto") return "반자동";
      return mode || "-";
    }

    function publisherChannelLabel(channel) {
      const c = String(channel || "").trim();
      return c || "-";
    }

    function monitorTargetNodeByStage(stage) {
      const s = String(stage || "").toLowerCase();
      if (s === "collect") return "collect.jobs";
      if (s === "label_content" || s === "label_image") return "label.results";
      if (s === "writer") return "writer.editor";
      if (s === "publish") return "publish.history";
      return "";
    }

    function monitorStageLabel(stage) {
      const s = String(stage || "").toLowerCase();
      return ENUM_LABELS.monitor_stage[s] || stage || "-";
    }

    function monitorLevelFromRow(row) {
      const status = String(row?.status || "").toLowerCase();
      const message = String(row?.message || "").toLowerCase();
      if (status.includes("fail") || status.includes("error") || message.includes("error") || message.includes("실패")) return "error";
      if (status.includes("queued") || status.includes("pending") || status.includes("retry") || message.includes("대기")) return "warn";
      return "info";
    }

    function monitorLevelClass(level) {
      const lv = String(level || "info").toLowerCase();
      if (lv === "error") return "fail";
      if (lv === "warn") return "warn";
      return "ok";
    }

    function monitorFailureGroupKey(row) {
      const msg = String(row?.message || "").toLowerCase();
      if (msg.includes("auth") || msg.includes("401") || msg.includes("403") || msg.includes("token")) return "인증";
      if (msg.includes("timeout") || msg.includes("network") || msg.includes("dns")) return "네트워크";
      if (msg.includes("429") || msg.includes("rate") || msg.includes("limit")) return "레이트리밋";
      if (msg.includes("format") || msg.includes("schema") || msg.includes("invalid")) return "포맷";
      return "기타";
    }

    function stopMonitorPolling() {
      if (!state.monitorPollTimer) return;
      clearInterval(state.monitorPollTimer);
      state.monitorPollTimer = null;
    }

    function startMonitorPolling() {
      stopMonitorPolling();
      if (!state.monitorStreamEnabled) return;
      const ms = Math.max(2, Math.min(60, Number(state.monitorPollSec || 5))) * 1000;
      state.monitorPollTimer = setInterval(() => {
        refreshMonitorSection().catch(() => {});
      }, ms);
    }

    async function retryMonitorRow(row) {
      const stage = String(row?.stage || "").toLowerCase();
      const msg = String(row?.message || "");
      if (stage === "publish") {
        const m = msg.match(/^(\d+)\s*\/\s*([^/]+)/);
        if (!m) throw new Error("발행 재시도에 필요한 article/channel 정보를 찾지 못했습니다.");
        const articleId = Number(m[1]);
        const channel = String(m[2] || "").trim();
        if (!articleId || !channel) throw new Error("재시도 대상 정보가 유효하지 않습니다.");
        await request("/api/publisher/enqueue", {
          method: "POST",
          body: JSON.stringify({ article_id: articleId, target_channel: channel, mode: "semi_auto" }),
        });
        showAlert(`재시도 큐에 추가했습니다. article=${articleId}, channel=${channel}`, "재시도", "success");
        return;
      }
      throw new Error("현재는 발행 단계 실패만 즉시 재시도를 지원합니다.");
    }

    function openMonitorRowDetail(row) {
      const detail = [
        `단계: ${monitorStageLabel(row.stage)}`,
        `레벨: ${monitorLevelFromRow(row)}`,
        `상태: ${row.status || "-"}`,
        `시각: ${fmt(row.time)}`,
        `메시지: ${row.message || "-"}`,
      ];
      showAlert(detail.join("\n"), "실패 상세", "info");
    }

    function monitorRowKey(row) {
      const stage = String(row?.stage || "");
      const entity = String(row?.entity_id || row?.message || "");
      return `${stage}:${entity}`;
    }

    function monitorBackoffSeconds(attemptCount, priority) {
      const base = Math.min(3600, Math.max(5, 2 ** Math.max(0, Number(attemptCount || 0))));
      const weight = Math.max(1, Number(priority || 1));
      return Math.max(5, Math.floor(base / weight));
    }

    function monitorRetryEntry(key) {
      const map = state.monitorRetryMeta || {};
      if (!map[key]) map[key] = { priority: 1, attempts: 0, last_attempt_at: "", message: "" };
      return map[key];
    }

    function renderMonitorRetryQueue(rows) {
      const retryBody = qs("#monitorRetryTable tbody");
      const archiveBody = qs("#monitorRetryArchiveTable tbody");
      if (!retryBody || !archiveBody) return;
      const maxRetry = Math.max(1, Math.min(20, Number(state.monitorRetryMax || 5)));
      const candidates = (rows || []).filter((r) => monitorLevelFromRow(r) === "error");
      const active = [];
      const archived = [];
      candidates.forEach((r) => {
        const key = monitorRowKey(r);
        const entry = monitorRetryEntry(key);
        entry.message = String(r.message || "");
        const target = Number(entry.attempts || 0) >= maxRetry ? archived : active;
        target.push({ key, row: r, entry });
      });
      active.sort((a, b) => Number(b.entry.priority || 1) - Number(a.entry.priority || 1));

      retryBody.innerHTML = active.length ? "" : "<tr><td colspan='6'>재시도 큐 없음</td></tr>";
      active.forEach((item) => {
        const backoff = monitorBackoffSeconds(item.entry.attempts, item.entry.priority);
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${escapeHtml(item.key)}</td><td>${Number(item.entry.priority || 1)}</td><td>${Number(item.entry.attempts || 0)}/${maxRetry}</td><td>${backoff}s</td><td>${escapeHtml(String(item.entry.message || "").slice(0, 120))}</td><td><button class='btn ghost' data-act='up'>승격</button> <button class='btn ghost' data-act='down'>강등</button> <button class='btn ghost' data-act='retry'>재시도</button></td>`;
        tr.querySelector("[data-act='up']")?.addEventListener("click", () => {
          item.entry.priority = Math.min(10, Number(item.entry.priority || 1) + 1);
          persistMonitorRetryMeta();
          renderMonitorRetryQueue(rows);
        });
        tr.querySelector("[data-act='down']")?.addEventListener("click", () => {
          item.entry.priority = Math.max(1, Number(item.entry.priority || 1) - 1);
          persistMonitorRetryMeta();
          renderMonitorRetryQueue(rows);
        });
        tr.querySelector("[data-act='retry']")?.addEventListener("click", () => {
          retryMonitorRow(item.row)
            .then(() => {
              item.entry.attempts = Number(item.entry.attempts || 0) + 1;
              item.entry.last_attempt_at = new Date().toISOString();
              persistMonitorRetryMeta();
              renderMonitorRetryQueue(rows);
            })
            .catch((err) => showAlert(String(err), "오류", "error"));
        });
        retryBody.appendChild(tr);
      });

      archiveBody.innerHTML = archived.length ? "" : "<tr><td colspan='4'>보관함 없음</td></tr>";
      archived.forEach((item) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${escapeHtml(item.key)}</td><td>${Number(item.entry.attempts || 0)}</td><td>${escapeHtml(String(item.entry.message || "").slice(0, 120))}</td><td>${fmt(item.entry.last_attempt_at)}</td>`;
        archiveBody.appendChild(tr);
      });

      const hint = qs("#monitorRetryHint");
      if (hint) hint.textContent = `재시도 큐 ${active.length}건 | 정책: 지수 backoff(2^n) / 우선순위 가중`;
      const archiveHint = qs("#monitorRetryArchiveHint");
      if (archiveHint) archiveHint.textContent = `최대 재시도(${maxRetry}) 초과 보관함: ${archived.length}건`;
    }

    async function refreshMonitorSection() {
      const query = new URLSearchParams();
      query.set("limit", "200");
      if (state.monitorCursor) query.set("cursor", state.monitorCursor);
      if (state.monitorStageFilter && state.monitorStageFilter !== "all") query.set("stage", state.monitorStageFilter);
      let payload = null;
      let labelStatusCounts = null;
      try {
        const [eventPayload, statusPayload] = await Promise.all([
          request(`/api/v2/monitor/events?${query.toString()}`),
          request("/api/labeling/status-counts").catch(() => null),
        ]);
        payload = eventPayload;
        labelStatusCounts = statusPayload;
      } catch (err) {
        const tbody = qs("#monitorTable tbody");
        if (tbody) tbody.innerHTML = "<tr><td colspan='6'>모니터 조회 실패</td></tr>";
        const cursorHint = qs("#monitorCursorHint");
        if (cursorHint) {
          const code = String(err?.code || "MONITOR_FETCH_ERROR");
          const reqId = String(err?.requestId || "-");
          cursorHint.textContent = `cursor=${state.monitorCursor || "-"} | next=- | 오류코드:${code} | request_id:${reqId}`;
        }
        throw err;
      }
      const rows = payload && Array.isArray(payload.items) ? payload.items : [];
      state.monitorLastRows = rows;
      state.monitorNextCursor = String(payload?.next_cursor || "");
      const node = state.menuNodeId || "monitor.logs";
      const stageFilterSelect = qs("#monitorStageFilter");
      if (stageFilterSelect && !stageFilterSelect.value) stageFilterSelect.value = state.monitorStageFilter || "all";
      const stageFilter = stageFilterSelect?.value || state.monitorStageFilter || "all";
      state.monitorStageFilter = stageFilter;
      const levelFilterSel = qs("#monitorLevelFilter");
      if (levelFilterSel && !levelFilterSel.value) levelFilterSel.value = state.monitorLevelFilter || "all";
      const levelFilter = levelFilterSel?.value || state.monitorLevelFilter || "all";
      state.monitorLevelFilter = levelFilter;

      const textFilterInput = qs("#monitorTextFilter");
      if (textFilterInput && !textFilterInput.value && state.monitorTextFilter) textFilterInput.value = state.monitorTextFilter;
      const textFilterRaw = String(textFilterInput?.value || state.monitorTextFilter || "").trim();
      const textFilter = textFilterRaw.toLowerCase();
      state.monitorTextFilter = textFilterRaw;
      const streamEnabled = !!qs("#monitorStreamEnabled")?.checked;
      const pollSec = Math.max(2, Math.min(60, Number(qs("#monitorPollSec")?.value || state.monitorPollSec || 5)));
      state.monitorStreamEnabled = streamEnabled;
      state.monitorPollSec = pollSec;

      let filtered = rows;
      if (stageFilter !== "all") {
        filtered = filtered.filter((r) => String(r.stage || "").toLowerCase() === stageFilter);
      }
      if (node === "monitor.failures") {
        filtered = filtered.filter((r) => {
          const s = String(r.status || "").toLowerCase();
          return s.includes("fail") || s.includes("error");
        });
      } else if (node === "monitor.retry") {
        filtered = filtered.filter((r) => {
          const s = String(r.status || "").toLowerCase();
          return s.includes("queued") || s.includes("pending") || s.includes("retry") || s.includes("fail");
        });
      }
      if (levelFilter !== "all") {
        filtered = filtered.filter((r) => monitorLevelFromRow(r) === levelFilter);
      }
      if (textFilter) {
        filtered = filtered.filter((r) => {
          const haystack = `${monitorStageLabel(r.stage)} ${r.stage || ""} ${r.status || ""} ${r.message || ""}`.toLowerCase();
          return haystack.includes(textFilter);
        });
      }

      const tbody = qs("#monitorTable tbody");
      if (!tbody) return;
      tbody.innerHTML = filtered.length ? "" : "<tr><td colspan='6'>데이터 없음</td></tr>";
      const grouped = {};
      filtered.forEach((r) => {
        if (monitorLevelFromRow(r) !== "error") return;
        const key = monitorFailureGroupKey(r);
        grouped[key] = Number(grouped[key] || 0) + 1;
      });
      filtered.slice(0, 200).forEach((r) => {
        const tr = document.createElement("tr");
        tr.classList.add("monitor-row");
        const level = monitorLevelFromRow(r);
        const levelClass = monitorLevelClass(level);
        const statusClass = monitorStatusClass(r.status);
        tr.innerHTML = `<td>${monitorStageLabel(r.stage)}</td><td><span class="badge-status ${levelClass}">${level}</span></td><td><span class="badge-status ${statusClass}">${r.status || "-"}</span></td><td>${r.message || "-"}</td><td>${fmt(r.time)}</td><td><button class="btn ghost" data-action="detail">상세</button>${level === "error" ? " <button class='btn ghost' data-action='retry'>재시도</button>" : ""}</td>`;
        const targetNode = monitorTargetNodeByStage(r.stage);
        if (targetNode) {
          tr.title = "클릭 시 관련 메뉴로 이동";
          tr.addEventListener("click", () => navigateToNode(targetNode));
        }
        tr.querySelector("[data-action='detail']")?.addEventListener("click", (e) => {
          e.stopPropagation();
          openMonitorRowDetail(r);
        });
        tr.querySelector("[data-action='retry']")?.addEventListener("click", (e) => {
          e.stopPropagation();
          retryMonitorRow(r).catch((err) => showAlert(String(err), "오류", "error"));
        });
        tbody.appendChild(tr);
      });

      const hint = qs("#monitorHint");
      if (hint) hint.textContent = `필터: ${node} / 단계:${stageFilter} / 레벨:${levelFilter} / 검색:${textFilterRaw || "-"} | 총 ${filtered.length}건 | 스트리밍 ${state.monitorStreamEnabled ? `ON(${state.monitorPollSec}s)` : "OFF"}`;
      const groupHint = qs("#monitorGroupHint");
      if (groupHint) {
        const text = Object.entries(grouped).map(([k, v]) => `${k}:${v}`).join(", ");
        groupHint.textContent = text ? `실패 원인 그룹: ${text}` : "실패 원인 그룹: 없음";
      }
      const labelStatusHintTotal = qs("#monitorLabelStatusHintTotal");
      const labelStatusHintContent = qs("#monitorLabelStatusHintContent");
      const labelStatusHintImage = qs("#monitorLabelStatusHintImage");
      if (labelStatusHintTotal || labelStatusHintContent || labelStatusHintImage) {
        const bucket = labelStatusCounts && typeof labelStatusCounts === "object" ? labelStatusCounts : {};
        const total = bucket.total || {};
        const content = bucket.content || {};
        const image = bucket.image || {};
        const toText = (v) => Number(v || 0);
        if (labelStatusHintTotal) {
          labelStatusHintTotal.textContent = `라벨 상태(전체) | pending:${toText(total.pending)} | rule_done:${toText(total.rule_done)} | free_api_done:${toText(total.free_api_done)} | paid_api_done:${toText(total.paid_api_done)} | completed:${toText(total.completed)}`;
        }
        if (labelStatusHintContent) {
          labelStatusHintContent.textContent = `라벨 상태(텍스트) | pending:${toText(content.pending)} | rule_done:${toText(content.rule_done)} | free_api_done:${toText(content.free_api_done)} | paid_api_done:${toText(content.paid_api_done)} | completed:${toText(content.completed)}`;
        }
        if (labelStatusHintImage) {
          labelStatusHintImage.textContent = `라벨 상태(이미지) | pending:${toText(image.pending)} | rule_done:${toText(image.rule_done)} | free_api_done:${toText(image.free_api_done)} | paid_api_done:${toText(image.paid_api_done)} | completed:${toText(image.completed)}`;
        }
      }
      const cursorHint = qs("#monitorCursorHint");
      if (cursorHint) {
        const err = payload?.error_code ? ` | 오류코드:${payload.error_code}` : "";
        cursorHint.textContent = `cursor=${state.monitorCursor || "-"} | next=${state.monitorNextCursor || "-"}${err}`;
      }
      renderMonitorRetryQueue(filtered);
      startMonitorPolling();
    }

    return {
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
    };
  }

  window.createMonitorModule = createMonitorModule;
})();
