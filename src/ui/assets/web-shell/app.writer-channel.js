(() => {
  function createWriterChannelModule(ctx) {
    const { qs, state, ENUM_LABELS } = ctx || {};

    function encodeWriterAuthReference(loginId, password, apiKey) {
      const lid = String(loginId || "").trim();
      const pwd = String(password || "").trim();
      const key = String(apiKey || "").trim();
      if (!lid && !pwd && !key) return "";
      return JSON.stringify({ login_id: lid, password: pwd, api_key: key });
    }

    function decodeWriterAuthReference(raw) {
      const text = String(raw || "").trim();
      if (!text) return { login_id: "", password: "", api_key: "" };
      try {
        const parsed = JSON.parse(text);
        if (parsed && typeof parsed === "object") {
          const legacySecret = String(parsed.secret || "");
          return {
            login_id: String(parsed.login_id || ""),
            password: String(parsed.password || legacySecret),
            api_key: String(parsed.api_key || ""),
          };
        }
      } catch (_e) {
        // fallback below
      }
      return { login_id: text, password: "", api_key: "" };
    }

    function maskedSecret(value) {
      const text = String(value || "");
      if (!text) return "";
      if (text.length <= 4) return "*".repeat(text.length);
      return `${text.slice(0, 2)}${"*".repeat(Math.max(2, text.length - 4))}${text.slice(-2)}`;
    }

    function writerChannelPayload() {
      const affiliateText = String(qs("#writerChannelAffiliateText")?.value || "").trim();
      const isUpdate = !!state.selectedWriterSettingChannelId;
      const snapshot = state.writerChannelAuthSnapshot || { login_id: "", password: "", api_key: "" };
      const loginIdInput = String(qs("#writerChannelLoginId")?.value || "").trim();
      const passwordInput = String(qs("#writerChannelPassword")?.value || "").trim();
      const apiKeyInput = String(qs("#writerChannelApiKey")?.value || "").trim();
      const loginId = isUpdate ? (loginIdInput || String(snapshot.login_id || "").trim()) : loginIdInput;
      const password = isUpdate ? (passwordInput || String(snapshot.password || "").trim()) : passwordInput;
      const apiKey = isUpdate ? (apiKeyInput || String(snapshot.api_key || "").trim()) : apiKeyInput;
      return {
        code: qs("#writerChannelCode").value || "",
        display_name: qs("#writerChannelName").value || "",
        channel_type: qs("#writerChannelType").value || "blog",
        connection_type: qs("#writerChannelConnection").value || "api",
        status: qs("#writerChannelStatus").value || "active",
        is_enabled: !!qs("#writerChannelEnabled").checked,
        auth_type: qs("#writerChannelAuthType").value || "",
        auth_reference: encodeWriterAuthReference(loginId, password, apiKey),
        api_endpoint_url: qs("#writerChannelApiUrl").value || "",
        affiliate_disclosure_required: !!qs("#writerChannelAffiliate").checked,
        notes: affiliateText,
      };
    }

    function validateWriterChannelPayload(payload) {
      if (!String(payload.code || "").trim()) throw new Error("채널 코드를 입력하세요.");
      if (!String(payload.display_name || "").trim()) throw new Error("채널명을 입력하세요.");
      if (state.selectedWriterSettingChannelId) {
        const original = String(state.writerChannelOriginalCode || "").trim();
        const incoming = String(payload.code || "").trim();
        if (original && incoming !== original) throw new Error("등록된 채널 코드는 변경할 수 없습니다. 새 채널을 생성하세요.");
      }
      if (payload.affiliate_disclosure_required && !String(payload.notes || "").trim()) {
        throw new Error("제휴문구 필수 사용 시 제휴 문구를 입력하세요.");
      }
    }

    function fillWriterChannelForm(row) {
      if (!row) return;
      state.writerChannelOriginalCode = String(row.code || "");
      qs("#writerChannelCode").value = row.code || "";
      qs("#writerChannelName").value = row.display_name || "";
      qs("#writerChannelType").value = row.channel_type || "blog";
      qs("#writerChannelConnection").value = row.connection_type || "api";
      qs("#writerChannelStatus").value = row.status || "active";
      qs("#writerChannelEnabled").checked = !!row.is_enabled;
      qs("#writerChannelAuthType").value = row.auth_type || "";
      const authInfo = decodeWriterAuthReference(row.auth_reference || "");
      state.writerChannelAuthSnapshot = {
        login_id: authInfo.login_id || "",
        password: authInfo.password || "",
        api_key: authInfo.api_key || "",
      };
      qs("#writerChannelLoginId").value = authInfo.login_id || "";
      qs("#writerChannelPassword").value = "";
      qs("#writerChannelPassword").placeholder = authInfo.password ? `기존 저장됨 (${maskedSecret(authInfo.password)})` : "미저장";
      qs("#writerChannelApiKey").value = "";
      qs("#writerChannelApiKey").placeholder = authInfo.api_key ? `기존 저장됨 (${maskedSecret(authInfo.api_key)})` : "미저장";
      qs("#writerChannelApiUrl").value = row.api_endpoint_url || "";
      qs("#writerChannelAffiliate").checked = !!row.affiliate_disclosure_required;
      qs("#writerChannelAffiliateText").value = row.notes || "";
      syncWriterChannelCodePolicy();
      syncWriterAuthChangeHint();
      syncWriterAffiliateTextState();
    }

    function resetWriterChannelFormForCreate() {
      state.selectedWriterSettingChannelId = null;
      state.writerChannelOriginalCode = "";
      state.writerChannelAuthSnapshot = { login_id: "", password: "", api_key: "" };
      if (qs("#writerChannelCode")) qs("#writerChannelCode").value = "";
      if (qs("#writerChannelName")) qs("#writerChannelName").value = "";
      if (qs("#writerChannelType")) qs("#writerChannelType").value = "blog";
      if (qs("#writerChannelConnection")) qs("#writerChannelConnection").value = "api";
      if (qs("#writerChannelStatus")) qs("#writerChannelStatus").value = "active";
      if (qs("#writerChannelEnabled")) qs("#writerChannelEnabled").checked = true;
      if (qs("#writerChannelAuthType")) qs("#writerChannelAuthType").value = "";
      if (qs("#writerChannelLoginId")) qs("#writerChannelLoginId").value = "";
      if (qs("#writerChannelPassword")) {
        qs("#writerChannelPassword").value = "";
        qs("#writerChannelPassword").placeholder = "선택 입력";
      }
      if (qs("#writerChannelApiKey")) {
        qs("#writerChannelApiKey").value = "";
        qs("#writerChannelApiKey").placeholder = "선택 입력";
      }
      if (qs("#writerChannelApiUrl")) qs("#writerChannelApiUrl").value = "";
      if (qs("#writerChannelAffiliate")) qs("#writerChannelAffiliate").checked = false;
      if (qs("#writerChannelAffiliateText")) qs("#writerChannelAffiliateText").value = "";
      syncWriterChannelCodePolicy();
      syncWriterAuthChangeHint();
      syncWriterAffiliateTextState();
    }

    function syncWriterChannelCodePolicy() {
      const codeInput = qs("#writerChannelCode");
      const hint = qs("#writerChannelCodePolicyHint");
      const isUpdate = !!state.selectedWriterSettingChannelId;
      if (codeInput) {
        codeInput.readOnly = isUpdate;
        codeInput.title = isUpdate ? "등록된 채널 코드는 변경할 수 없습니다." : "";
      }
      if (hint) {
        hint.textContent = isUpdate
          ? "코드 정책: 등록된 채널 코드는 고정입니다. 변경이 필요하면 새 채널을 생성하세요."
          : "코드 정책: 신규 생성 시 코드 확정 후 변경 불가";
      }
    }

    function syncWriterAuthChangeHint() {
      const hint = qs("#writerAuthChangeHint");
      if (!hint) return;
      const snapshot = state.writerChannelAuthSnapshot || { login_id: "", password: "", api_key: "" };
      const loginChanged = String(qs("#writerChannelLoginId")?.value || "").trim() !== String(snapshot.login_id || "").trim();
      const passwordChanged = String(qs("#writerChannelPassword")?.value || "").trim().length > 0;
      const apiChanged = String(qs("#writerChannelApiKey")?.value || "").trim().length > 0;
      const changed = [];
      if (loginChanged) changed.push("로그인 ID");
      if (passwordChanged) changed.push("비밀번호");
      if (apiChanged) changed.push("API 키");
      hint.textContent = changed.length ? `인증정보 변경 예정: ${changed.join(", ")}` : "인증정보 변경 없음";
    }

    function syncWriterAffiliateTextState() {
      const toggle = qs("#writerChannelAffiliate");
      const text = qs("#writerChannelAffiliateText");
      if (!toggle || !text) return;
      const required = !!toggle.checked;
      text.disabled = !required;
      if (required) {
        text.setAttribute("required", "required");
        text.placeholder = "예: 이 글에는 제휴 링크가 포함될 수 있으며, 구매 시 수수료를 받을 수 있습니다.";
      } else {
        text.removeAttribute("required");
        text.placeholder = "제휴문구 필수 사용 시 입력";
      }
      syncWriterChannelSwitches();
    }

    function syncWriterSwitchVisual(inputId) {
      const input = qs(`#${inputId}`);
      if (!input) return;
      const root = input.closest(".switch");
      if (!root) return;
      root.setAttribute("data-on", input.checked ? "true" : "false");
    }

    function syncWriterChannelSwitches() {
      syncWriterSwitchVisual("writerChannelEnabled");
      syncWriterSwitchVisual("writerChannelAffiliate");
    }

    function writerChannelTypeLabel(value) {
      const key = String(value || "blog");
      return ENUM_LABELS.writer_channel_type[key] || key;
    }

    function writerChannelConnectionLabel(value) {
      const key = String(value || "api");
      return ENUM_LABELS.writer_channel_connection[key] || key;
    }

    function writerChannelStatusLabel(value) {
      const key = String(value || "active");
      return ENUM_LABELS.writer_channel_status[key] || key;
    }

    function writerChannelStatusClass(value) {
      const key = String(value || "active");
      if (key === "active") return "ok";
      if (key === "expiring") return "warn";
      if (key === "auth_error") return "fail";
      return "neutral";
    }

    return {
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
    };
  }

  window.createWriterChannelModule = createWriterChannelModule;
})();
