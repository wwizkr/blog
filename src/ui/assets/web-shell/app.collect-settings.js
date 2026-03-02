(() => {
  function createCollectSettingsModule(ctx) {
    const { qs, state, request, showAlert, showConfirm } = ctx || {};

    function getCollectScopeValue() {
      return qs("input[name='collectSettingScope']:checked")?.value || "selected";
    }

    function setCollectScopeValue(value) {
      const normalized = value === "all" || value === "related" ? value : "selected";
      const target = qs(`input[name='collectSettingScope'][value='${normalized}']`) || qs("#collectScopeSelected");
      if (target) target.checked = true;
    }

    function getCollectChecklistRows(kind) {
      const isChannel = kind === "channel";
      const rows = isChannel ? (state.collectSettingChannels || []) : (state.collectSettingCategories || []);
      const query = String(isChannel ? state.collectSettingChannelSearch : state.collectSettingCategorySearch).trim().toLowerCase();
      if (!query) return rows;
      return rows.filter((row) => {
        const hay = isChannel
          ? `${row.display_name || ""} ${row.code || ""}`.toLowerCase()
          : `${row.name || ""}`.toLowerCase();
        return hay.includes(query);
      });
    }

    function getCollectSettingPayload() {
      return {
        keyword_scope: getCollectScopeValue(),
        interval_minutes: Number(qs("#collectSettingInterval").value || 60),
        max_results: Number(qs("#collectSettingMaxResults").value || 3),
        request_timeout: Number(qs("#collectSettingTimeout").value || 15),
        retry_count: Number(qs("#collectSettingRetry").value || 1),
        selected_channel_codes: state.collectSettingChannelCodes,
        selected_category_ids: state.collectSettingCategoryIds,
        naver_related_sync: !!qs("#collectSettingNaverRelated").checked,
      };
    }

    function validateCollectSettingInputs() {
      const payload = getCollectSettingPayload();
      const errors = [];
      if (payload.interval_minutes < 5 || payload.interval_minutes > 1440) errors.push("수집 주기(분)는 5~1440 범위여야 합니다.");
      if (payload.max_results < 1 || payload.max_results > 20) errors.push("키워드당 최대 수집은 1~20 범위여야 합니다.");
      if (payload.request_timeout < 3 || payload.request_timeout > 120) errors.push("타임아웃(초)는 3~120 범위여야 합니다.");
      if (payload.retry_count < 0 || payload.retry_count > 5) errors.push("재시도(회)는 0~5 범위여야 합니다.");
      return errors;
    }

    function normalizeCollectSettingSnapshot(payload) {
      const p = payload || {};
      const channelCodes = [...new Set((p.selected_channel_codes || []).map((v) => String(v)))].sort();
      const categoryIds = [...new Set((p.selected_category_ids || []).map((v) => Number(v)).filter((v) => Number.isFinite(v)))].sort((a, b) => a - b);
      return {
        keyword_scope: String(p.keyword_scope || "selected"),
        interval_minutes: Number(p.interval_minutes || 60),
        max_results: Number(p.max_results || 3),
        request_timeout: Number(p.request_timeout || 15),
        retry_count: Number(p.retry_count || 1),
        selected_channel_codes: channelCodes,
        selected_category_ids: categoryIds,
        naver_related_sync: !!p.naver_related_sync,
      };
    }

    function collectSettingDiffLines(prevRaw, nextRaw) {
      const prev = normalizeCollectSettingSnapshot(prevRaw);
      const next = normalizeCollectSettingSnapshot(nextRaw);
      const lines = [];
      if (prev.keyword_scope !== next.keyword_scope) lines.push(`수집 범위: ${prev.keyword_scope} -> ${next.keyword_scope}`);
      if (prev.interval_minutes !== next.interval_minutes) lines.push(`수집 주기: ${prev.interval_minutes} -> ${next.interval_minutes}`);
      if (prev.max_results !== next.max_results) lines.push(`최대 수집: ${prev.max_results} -> ${next.max_results}`);
      if (prev.request_timeout !== next.request_timeout) lines.push(`타임아웃: ${prev.request_timeout} -> ${next.request_timeout}`);
      if (prev.retry_count !== next.retry_count) lines.push(`재시도: ${prev.retry_count} -> ${next.retry_count}`);
      if (prev.naver_related_sync !== next.naver_related_sync) lines.push(`네이버 연관 동기화: ${prev.naver_related_sync ? "Y" : "N"} -> ${next.naver_related_sync ? "Y" : "N"}`);
      if (prev.selected_channel_codes.join(",") !== next.selected_channel_codes.join(",")) {
        lines.push(`선택 채널: ${prev.selected_channel_codes.length} -> ${next.selected_channel_codes.length}`);
      }
      if (prev.selected_category_ids.join(",") !== next.selected_category_ids.join(",")) {
        lines.push(`선택 카테고리: ${prev.selected_category_ids.length} -> ${next.selected_category_ids.length}`);
      }
      return lines;
    }

    function refreshCollectSettingHints() {
      const errors = validateCollectSettingInputs();
      const validationHint = qs("#collectSettingValidationHint");
      if (validationHint) validationHint.textContent = errors.length ? `검증 오류: ${errors.join(" / ")}` : "입력값 검증: 정상";
      const diffNode = qs("#collectSettingDiffPreview");
      const diff = collectSettingDiffLines(state.collectSettingsSnapshot || {}, getCollectSettingPayload());
      if (diffNode) diffNode.textContent = diff.length ? `변경사항: ${diff.join(" | ")}` : "변경사항 없음";
      const saveBtn = qs("#collectSettingSaveBtn");
      if (saveBtn) saveBtn.disabled = errors.length > 0;
    }

    function updateCollectChecklistMeta(kind) {
      const isChannel = kind === "channel";
      const rows = getCollectChecklistRows(kind);
      const selected = isChannel ? new Set(state.collectSettingChannelCodes) : new Set((state.collectSettingCategoryIds || []).map((v) => Number(v)));
      const selectedCount = rows.filter((row) => selected.has(isChannel ? String(row.code) : Number(row.id))).length;
      const total = rows.length;
      const countNode = qs(isChannel ? "#collectChannelCount" : "#collectCategoryCount");
      if (countNode) countNode.textContent = `${selectedCount}/${total}`;
      const allNode = qs(isChannel ? "#collectChannelAll" : "#collectCategoryAll");
      if (allNode) {
        allNode.checked = total > 0 && selectedCount === total;
        allNode.indeterminate = selectedCount > 0 && selectedCount < total;
      }
    }

    function renderCollectChecklist(kind) {
      const isChannel = kind === "channel";
      const rows = getCollectChecklistRows(kind);
      const wrap = qs(isChannel ? "#collectChannelChecklist" : "#collectCategoryChecklist");
      if (!wrap) return;
      wrap.innerHTML = "";

      if (!rows.length) {
        const query = String(isChannel ? state.collectSettingChannelSearch : state.collectSettingCategorySearch).trim();
        wrap.innerHTML = `<div class='check-empty'>${query ? "검색 결과 없음" : "항목 없음"}</div>`;
        updateCollectChecklistMeta(kind);
        return;
      }

      const selected = isChannel ? new Set(state.collectSettingChannelCodes) : new Set((state.collectSettingCategoryIds || []).map((v) => Number(v)));
      rows.forEach((row) => {
        const value = isChannel ? String(row.code) : Number(row.id);
        const label = isChannel ? `${row.display_name} (${row.code})` : String(row.name || "-");
        const item = document.createElement("label");
        item.className = "check-item";
        const input = document.createElement("input");
        input.type = "checkbox";
        input.value = String(value);
        input.checked = selected.has(value);
        input.addEventListener("change", () => {
          if (isChannel) {
            const next = new Set(state.collectSettingChannelCodes);
            if (input.checked) next.add(String(value));
            else next.delete(String(value));
            state.collectSettingChannelCodes = [...next];
          } else {
            const next = new Set((state.collectSettingCategoryIds || []).map((v) => Number(v)));
            if (input.checked) next.add(Number(value));
            else next.delete(Number(value));
            state.collectSettingCategoryIds = [...next];
          }
          updateCollectChecklistMeta(kind);
          refreshCollectSettingHints();
        });
        const text = document.createElement("span");
        text.textContent = label;
        item.appendChild(input);
        item.appendChild(text);
        if (isChannel && row.is_enabled === false) {
          const muted = document.createElement("span");
          muted.className = "muted";
          muted.textContent = "비활성";
          item.appendChild(muted);
        }
        wrap.appendChild(item);
      });
      updateCollectChecklistMeta(kind);
    }

    function toggleCollectChecklistAll(kind, checked) {
      const isChannel = kind === "channel";
      const rows = getCollectChecklistRows(kind);
      if (isChannel) {
        if (checked) {
          const next = new Set(state.collectSettingChannelCodes || []);
          rows.forEach((row) => next.add(String(row.code)));
          state.collectSettingChannelCodes = [...next];
        } else {
          const removeSet = new Set(rows.map((row) => String(row.code)));
          state.collectSettingChannelCodes = (state.collectSettingChannelCodes || []).filter((code) => !removeSet.has(String(code)));
        }
      } else if (checked) {
        const next = new Set((state.collectSettingCategoryIds || []).map((v) => Number(v)));
        rows.forEach((row) => next.add(Number(row.id)));
        state.collectSettingCategoryIds = [...next];
      } else {
        const removeSet = new Set(rows.map((row) => Number(row.id)));
        state.collectSettingCategoryIds = (state.collectSettingCategoryIds || []).filter((id) => !removeSet.has(Number(id)));
      }
      renderCollectChecklist(kind);
      refreshCollectSettingHints();
    }

    async function refreshCollectSettingsSection() {
      const [s, channels, categories] = await Promise.all([
        request("/api/v2/settings/collect"),
        request("/api/source-channels"),
        request("/api/categories"),
      ]);

      state.collectSettingChannels = channels || [];
      state.collectSettingCategories = categories || [];
      state.collectSettingChannelCodes = (s.selected_channel_codes || []).map((v) => String(v));
      state.collectSettingCategoryIds = (s.selected_category_ids || []).map((v) => Number(v)).filter((v) => Number.isFinite(v));
      state.collectSettingsSnapshot = normalizeCollectSettingSnapshot({
        keyword_scope: s.keyword_scope || "selected",
        interval_minutes: s.interval_minutes || 60,
        max_results: s.max_results || 3,
        request_timeout: s.request_timeout || 15,
        retry_count: s.retry_count || 1,
        selected_channel_codes: state.collectSettingChannelCodes,
        selected_category_ids: state.collectSettingCategoryIds,
        naver_related_sync: !!s.naver_related_sync,
      });

      setCollectScopeValue(s.keyword_scope || "selected");
      qs("#collectSettingInterval").value = s.interval_minutes || 60;
      qs("#collectSettingMaxResults").value = s.max_results || 3;
      qs("#collectSettingTimeout").value = s.request_timeout || 15;
      qs("#collectSettingRetry").value = s.retry_count || 1;
      qs("#collectSettingNaverRelated").checked = !!s.naver_related_sync;

      renderCollectChecklist("channel");
      renderCollectChecklist("category");
      refreshCollectSettingHints();
    }

    async function saveCollectSettingsSection() {
      const errors = validateCollectSettingInputs();
      if (errors.length) throw new Error(errors[0]);
      const payload = getCollectSettingPayload();
      const diff = collectSettingDiffLines(state.collectSettingsSnapshot || {}, payload);
      if (!diff.length) {
        showAlert("변경사항이 없습니다.", "안내", "warn");
        return;
      }
      const ok = await showConfirm(`아래 변경사항으로 저장할까요?\n${diff.join("\n")}`, "저장 확인", "warn");
      if (!ok) return;
      await request("/api/v2/settings/collect", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.collectSettingsSnapshot = normalizeCollectSettingSnapshot(payload);
      refreshCollectSettingHints();
    }

    return {
      getCollectScopeValue,
      setCollectScopeValue,
      getCollectChecklistRows,
      getCollectSettingPayload,
      validateCollectSettingInputs,
      normalizeCollectSettingSnapshot,
      collectSettingDiffLines,
      refreshCollectSettingHints,
      updateCollectChecklistMeta,
      renderCollectChecklist,
      toggleCollectChecklistAll,
      refreshCollectSettingsSection,
      saveCollectSettingsSection,
    };
  }

  window.createCollectSettingsModule = createCollectSettingsModule;
})();
