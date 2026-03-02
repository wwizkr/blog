(() => {
  function createManageModule(ctx) {
    const { qs, qsa, state, request, safeRequest, showAlert, escapeHtml } = ctx || {};

    async function refreshPersonaSection() {
      const rows = await request("/api/personas");
      state.personaRows = Array.isArray(rows) ? rows : [];
      const search = String(state.personaSearch || "").trim().toLowerCase();
      const activeFilter = String(state.personaActiveFilter || "all");
      const filtered = state.personaRows.filter((r) => {
        if (activeFilter === "active" && !r.is_active) return false;
        if (activeFilter === "inactive" && !!r.is_active) return false;
        if (!search) return true;
        const hay = `${r.name || ""} ${r.tone || ""} ${r.personality || ""} ${r.speech_style || ""}`.toLowerCase();
        return hay.includes(search);
      });
      const list = qs("#personaCardList");
      if (!list) return;
      list.innerHTML = "";
      if (!filtered.length) {
        state.selectedPersonaId = null;
        list.innerHTML = "<div class='manage-card-empty'>조건에 맞는 페르소나 없음</div>";
        syncManageSwitchVisuals();
        await refreshPersonaCollisionHint();
        return;
      }
      let selectedExists = false;
      let selectedRow = null;
      filtered.forEach((r) => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "manage-card";
        if (state.selectedPersonaId === r.id) {
          card.classList.add("selected");
          selectedExists = true;
          selectedRow = r;
        }
        const summary = [r.age_group, r.gender, r.speech_style].filter((v) => !!String(v || "").trim()).join(" / ");
        card.innerHTML = `
          <div class="manage-card-head">
            <div class="manage-card-title">${escapeHtml(r.name || "-")}</div>
            <span class="badge-status ${r.is_active ? "ok" : "neutral"}">${r.is_active ? "활성" : "비활성"}</span>
          </div>
          <div class="manage-card-sub">${escapeHtml(summary || "-")}</div>
          <div class="manage-card-meta">
            <span class="badge-channel">${escapeHtml(r.tone || "톤 미지정")}</span>
            <span class="badge-channel">${escapeHtml(r.personality || "성격 미지정")}</span>
          </div>
        `;
        card.addEventListener("click", () => {
          state.selectedPersonaId = r.id;
          qsa("#personaCardList .manage-card").forEach((el) => el.classList.remove("selected"));
          card.classList.add("selected");
          fillPersonaForm(r);
        });
        list.appendChild(card);
      });
      if (!selectedExists) {
        state.selectedPersonaId = null;
      } else if (selectedRow) {
        fillPersonaForm(selectedRow);
      }
      syncManageSwitchVisuals();
      await refreshPersonaCollisionHint();
    }

    function personaPayload() {
      return {
        name: qs("#personaName").value || "",
        age_group: qs("#personaAge").value || "",
        gender: qs("#personaGender").value || "",
        personality: qs("#personaPersonality").value || "",
        interests: qs("#personaInterests").value || "",
        speech_style: qs("#personaSpeech").value || "",
        tone: qs("#personaTone").value || "",
        style_guide: qs("#personaStyle").value || "",
        banned_words: qs("#personaBanned").value || "",
        is_active: !!qs("#personaActive").checked,
      };
    }

    function personaPreviewText(payload) {
      const name = String(payload.name || "기본 페르소나").trim() || "기본 페르소나";
      const tone = String(payload.tone || "정보형").trim() || "정보형";
      const speech = String(payload.speech_style || "명확하고 간결한 설명").trim() || "명확하고 간결한 설명";
      const style = String(payload.style_guide || "핵심을 먼저 제시하고 단계별로 설명").trim() || "핵심을 먼저 제시하고 단계별로 설명";
      return `[${name}] 톤=${tone}\n${speech} 어조로 작성합니다.\n${style}\n예시: 핵심 결론부터 짧게 제시하고, 근거를 3가지로 정리합니다.`;
    }

    function bannedWordsFromText(text) {
      return String(text || "")
        .split(",")
        .map((v) => v.trim().toLowerCase())
        .filter(Boolean);
    }

    async function refreshPersonaCollisionHint() {
      const hint = qs("#personaCollisionHint");
      if (!hint) return;
      const banned = bannedWordsFromText(qs("#personaBanned")?.value || "");
      if (!banned.length) {
        hint.textContent = "금칙어 충돌 없음";
        return;
      }
      const [templates, channels] = await Promise.all([
        safeRequest("/api/templates"),
        safeRequest("/api/writer-channels"),
      ]);
      const templateRows = templates.ok && Array.isArray(templates.data) ? templates.data : [];
      const channelRows = channels.ok && Array.isArray(channels.data) ? channels.data : [];
      const hits = [];
      templateRows.forEach((row) => {
        const hay = `${row.name || ""} ${row.user_prompt || ""}`.toLowerCase();
        if (banned.some((w) => hay.includes(w))) hits.push(`템플릿:${row.name || row.id}`);
      });
      channelRows.forEach((row) => {
        const hay = `${row.display_name || ""} ${row.notes || ""}`.toLowerCase();
        if (banned.some((w) => hay.includes(w))) hits.push(`채널:${row.display_name || row.code || row.id}`);
      });
      hint.textContent = hits.length ? `금칙어 충돌 감지 (${hits.length}건): ${hits.slice(0, 5).join(", ")}` : "금칙어 충돌 없음";
    }

    async function refreshTemplateSection() {
      const rows = await request("/api/templates");
      state.templateRows = Array.isArray(rows) ? rows : [];
      const list = qs("#templateCardList");
      if (!list) return;
      list.innerHTML = "";
      if (!rows.length) {
        state.selectedTemplateId = null;
        list.innerHTML = "<div class='manage-card-empty'>템플릿 없음</div>";
        syncManageSwitchVisuals();
        return;
      }
      let selectedExists = false;
      let selectedRow = null;
      state.templateRows.forEach((r) => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "manage-card";
        if (state.selectedTemplateId === r.id) {
          card.classList.add("selected");
          selectedExists = true;
          selectedRow = r;
        }
        card.innerHTML = `
          <div class="manage-card-head">
            <div class="manage-card-title">${escapeHtml(r.name || "-")}</div>
            <span class="badge-status ${r.is_active ? "ok" : "neutral"}">${r.is_active ? "활성" : "비활성"}</span>
          </div>
          <div class="manage-card-sub">v${escapeHtml(String(r.version || 1))}</div>
          <div class="manage-card-meta">
            <span class="badge-channel">${escapeHtml(r.template_type || "blog")}</span>
            <span class="badge-channel">${r.user_prompt ? "프롬프트 있음" : "프롬프트 없음"}</span>
          </div>
        `;
        card.addEventListener("click", () => {
          state.selectedTemplateId = r.id;
          qsa("#templateCardList .manage-card").forEach((el) => el.classList.remove("selected"));
          card.classList.add("selected");
          fillTemplateForm(r);
        });
        list.appendChild(card);
      });
      if (!selectedExists) {
        state.selectedTemplateId = null;
        state.templateSelectedSnapshot = null;
      } else if (selectedRow) {
        fillTemplateForm(selectedRow);
      }
      syncManageSwitchVisuals();
    }

    function templatePayload() {
      return {
        name: qs("#templateName").value || "",
        template_type: qs("#templateType").value || "blog",
        version: Number(qs("#templateVersion").value || 1),
        is_active: !!qs("#templateActive").checked,
        user_prompt: qs("#templatePrompt").value || "",
        output_schema: qs("#templateSchema").value || "",
      };
    }

    function templateTestRender(payload, sampleText) {
      const prompt = String(payload.user_prompt || "");
      const raw = String(sampleText || "").trim();
      const map = {};
      raw.split(",").forEach((part) => {
        const [k, ...rest] = part.split("=");
        const key = String(k || "").trim();
        if (!key) return;
        map[key] = rest.join("=").trim();
      });
      const defaultMap = {
        keyword: map.keyword || "샘플 키워드",
        persona_name: map.persona_name || "기본 페르소나",
        source_summary: map.source_summary || "샘플 요약 본문",
        persona_tone: map.persona_tone || "정보형",
      };
      return prompt.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_m, key) => {
        return Object.prototype.hasOwnProperty.call(map, key) ? String(map[key]) : (defaultMap[key] || `{${key}}`);
      });
    }

    function textDiffLines(a, b) {
      const left = String(a || "").split(/\r?\n/);
      const right = String(b || "").split(/\r?\n/);
      const maxLen = Math.max(left.length, right.length);
      const out = [];
      for (let i = 0; i < maxLen; i += 1) {
        const l = left[i];
        const r = right[i];
        if (l === r) continue;
        if (typeof l !== "undefined") out.push(`- ${l}`);
        if (typeof r !== "undefined") out.push(`+ ${r}`);
        if (out.length >= 120) break;
      }
      return out;
    }

    function showTemplateDiff() {
      if (!state.selectedTemplateId) throw new Error("비교할 템플릿을 선택하세요.");
      const current = templatePayload();
      const base = state.templateSelectedSnapshot || {};
      const lines = [
        `템플릿 Diff: ${base.name || current.name || "-"}`,
        `- version: ${base.version || 1} -> ${current.version || 1}`,
      ];
      const diff = textDiffLines(base.user_prompt || "", current.user_prompt || "");
      if (!diff.length) lines.push("프롬프트 변경사항 없음");
      else lines.push(...diff);
      showAlert(lines.join("\n"), "템플릿 Diff", "info");
    }

    async function cloneTemplateAsNewVersion() {
      if (!state.selectedTemplateId) throw new Error("복제할 템플릿을 선택하세요.");
      const payload = templatePayload();
      const newVersion = Math.max(1, Number(payload.version || 1) + 1);
      const newName = `${String(payload.name || "template").trim()} v${newVersion}`;
      await request("/api/templates", {
        method: "POST",
        body: JSON.stringify({
          name: newName,
          template_type: payload.template_type,
          user_prompt: payload.user_prompt,
          output_schema: payload.output_schema,
        }),
      });
      await refreshTemplateSection();
      showAlert(`새 버전 템플릿이 생성되었습니다: ${newName}`, "성공", "success");
    }

    function runTemplateTest() {
      const payload = templatePayload();
      const sample = String(qs("#templateTestSample")?.value || "");
      if (!payload.user_prompt) throw new Error("템플릿 프롬프트를 입력하세요.");
      const rendered = templateTestRender(payload, sample);
      if (qs("#templateTestHint")) qs("#templateTestHint").textContent = `테스트 렌더 길이: ${rendered.length}자`;
      showAlert(rendered, "템플릿 테스트 결과", "info");
    }

    async function refreshProviderSection() {
      const rows = await request("/api/ai-providers");
      state.providerRows = Array.isArray(rows) ? rows : [];
      const list = qs("#providerCardList");
      if (!list) return;
      list.innerHTML = "";
      if (!rows.length) {
        state.selectedProviderId = null;
        list.innerHTML = "<div class='manage-card-empty'>Provider 없음</div>";
        syncManageSwitchVisuals();
        return;
      }
      let selectedExists = false;
      let selectedRow = null;
      state.providerRows.forEach((r) => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "manage-card";
        if (state.selectedProviderId === r.id) {
          card.classList.add("selected");
          selectedExists = true;
          selectedRow = r;
        }
        const statusClass = r.status === "ready" ? "ok" : (r.status === "error" || r.status === "blocked" ? "fail" : "neutral");
        card.innerHTML = `
          <div class="manage-card-head">
            <div class="manage-card-title">${escapeHtml(r.provider || "-")}</div>
            <span class="badge-status ${r.is_enabled ? "ok" : "neutral"}">${r.is_enabled ? "활성" : "비활성"}</span>
          </div>
          <div class="manage-card-sub">${escapeHtml(r.model_name || "-")}</div>
          <div class="manage-card-meta">
            <span class="badge-status ${statusClass}">${escapeHtml(r.status || "unknown")}</span>
            <span class="badge-channel">${r.is_paid ? "유료" : "무료"}</span>
            <span class="badge-channel">p${escapeHtml(String(r.priority || 1))}</span>
          </div>
        `;
        card.addEventListener("click", () => {
          state.selectedProviderId = r.id;
          qsa("#providerCardList .manage-card").forEach((el) => el.classList.remove("selected"));
          card.classList.add("selected");
          fillProviderForm(r);
        });
        list.appendChild(card);
      });
      if (!selectedExists) {
        state.selectedProviderId = null;
      } else if (selectedRow) {
        fillProviderForm(selectedRow);
      }
      syncManageSwitchVisuals();
      await refreshProviderAliasHint();
    }

    function providerPayload() {
      return {
        provider: qs("#providerName").value || "",
        model_name: qs("#providerModel").value || "",
        api_key_alias: qs("#providerAlias").value || "",
        is_paid: !!qs("#providerPaid").checked,
        is_enabled: !!qs("#providerEnabled").checked,
        priority: Number(qs("#providerPriority").value || 1),
        rate_limit_per_min: Number(qs("#providerRpm").value || 0) || null,
        daily_budget_limit: Number(qs("#providerBudget").value || 0) || null,
        status: qs("#providerStatus").value || "unknown",
      };
    }

    async function refreshProviderAliasHint() {
      const hint = qs("#providerAliasHint");
      if (!hint) return;
      const map = await request("/api/ai-providers/env-status").catch(() => ({ items: [] }));
      const items = Array.isArray(map.items) ? map.items : [];
      const missing = items.filter((x) => !x.exists).map((x) => x.alias);
      hint.textContent = missing.length
        ? `Alias 미존재: ${missing.join(", ")}`
        : "모든 API Key Alias 환경변수 확인됨";
    }

    async function normalizeProviderPriorities() {
      const rows = [...(state.providerRows || [])].sort((a, b) => Number(a.priority || 999) - Number(b.priority || 999));
      for (let i = 0; i < rows.length; i += 1) {
        const row = rows[i];
        const nextPriority = i + 1;
        if (Number(row.priority || 0) === nextPriority) continue;
        await request(`/api/ai-providers/${row.id}/update`, {
          method: "POST",
          body: JSON.stringify({
            provider: row.provider || "",
            model_name: row.model_name || "",
            api_key_alias: row.api_key_alias || "",
            is_paid: !!row.is_paid,
            is_enabled: !!row.is_enabled,
            priority: nextPriority,
            rate_limit_per_min: row.rate_limit_per_min,
            daily_budget_limit: row.daily_budget_limit,
            status: row.status || "unknown",
          }),
        });
      }
      await refreshProviderSection();
      showAlert("우선순위를 자동 재정렬했습니다.", "성공", "success");
    }

    async function healthCheckProvider() {
      if (!state.selectedProviderId) throw new Error("상태 체크할 API를 선택하세요.");
      const result = await request(`/api/ai-providers/${state.selectedProviderId}/health-check`, { method: "POST", body: "{}" });
      const statusText = result?.ok ? "정상" : "오류";
      showAlert(`${statusText}\n${result?.message || "-"}`, "상태 체크", result?.ok ? "success" : "warn");
      await refreshProviderSection();
    }

    function fillPersonaForm(row) {
      if (!row) return;
      qs("#personaName").value = row.name || "";
      qs("#personaAge").value = row.age_group || "";
      qs("#personaGender").value = row.gender || "";
      qs("#personaPersonality").value = row.personality || "";
      qs("#personaInterests").value = row.interests || "";
      qs("#personaSpeech").value = row.speech_style || "";
      qs("#personaTone").value = row.tone || "";
      qs("#personaStyle").value = row.style_guide || "";
      qs("#personaBanned").value = row.banned_words || "";
      qs("#personaActive").checked = !!row.is_active;
      syncManageSwitchVisuals();
    }

    function fillTemplateForm(row) {
      if (!row) return;
      state.templateSelectedSnapshot = { ...row };
      qs("#templateName").value = row.name || "";
      qs("#templateType").value = row.template_type || "blog";
      qs("#templateVersion").value = row.version || 1;
      qs("#templateActive").checked = !!row.is_active;
      qs("#templatePrompt").value = row.user_prompt || "";
      qs("#templateSchema").value = row.output_schema || "";
      syncManageSwitchVisuals();
    }

    function fillProviderForm(row) {
      if (!row) return;
      qs("#providerName").value = row.provider || "";
      qs("#providerModel").value = row.model_name || "";
      qs("#providerAlias").value = row.api_key_alias || "";
      qs("#providerPaid").checked = !!row.is_paid;
      qs("#providerEnabled").checked = !!row.is_enabled;
      qs("#providerPriority").value = row.priority || 1;
      qs("#providerRpm").value = row.rate_limit_per_min || 0;
      qs("#providerBudget").value = row.daily_budget_limit || 0;
      qs("#providerStatus").value = row.status || "unknown";
      syncManageSwitchVisuals();
    }

    function syncManageSwitchVisual(inputId) {
      const input = qs(`#${inputId}`);
      if (!input) return;
      const root = input.closest(".switch-inline");
      if (!root) return;
      root.setAttribute("data-on", input.checked ? "true" : "false");
    }

    function syncManageSwitchVisuals() {
      syncManageSwitchVisual("personaActive");
      syncManageSwitchVisual("templateActive");
      syncManageSwitchVisual("providerPaid");
      syncManageSwitchVisual("providerEnabled");
    }

    return {
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
    };
  }

  window.createManageModule = createManageModule;
})();
