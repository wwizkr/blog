(() => {
  function createPublishSettingsModule(ctx) {
    const {
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
    } = ctx || {};

    function publishModeLabel(value) {
      const m = String(value || "semi_auto");
      return ENUM_LABELS.publish_mode[m] || m;
    }

    function publishFormatLabel(value) {
      const v = String(value || "blog");
      return ENUM_LABELS.publish_format[v] || v;
    }

    function publishStyleLabel(value) {
      const v = String(value || "informative");
      return ENUM_LABELS.publish_style[v] || v;
    }

    function normalizePublishSettingSnapshot(payload) {
      return {
        channel_code: String(payload.channel_code || ""),
        api_url: String(payload.api_url || ""),
        publish_cycle_minutes: Number(payload.publish_cycle_minutes || 60),
        publish_mode: String(payload.publish_mode || "semi_auto"),
        publish_format: String(payload.publish_format || "blog"),
        writing_style: String(payload.writing_style || "informative"),
      };
    }

    function currentPublishSettingFormPayload() {
      return {
        channel_code: qs("#publishSettingChannel")?.value || "",
        api_url: qs("#publishSettingApi")?.value || "",
        publish_cycle_minutes: Number(qs("#publishSettingCycle")?.value || 60),
        publish_mode: qs("#publishSettingMode")?.value || "semi_auto",
        publish_format: qs("#publishSettingFormat")?.value || "blog",
        writing_style: qs("#publishSettingStyle")?.value || "informative",
      };
    }

    function publishSettingDiffLines(prev, next) {
      const a = normalizePublishSettingSnapshot(prev || {});
      const b = normalizePublishSettingSnapshot(next || {});
      const lines = [];
      if (a.publish_cycle_minutes !== b.publish_cycle_minutes) lines.push(`주기: ${a.publish_cycle_minutes} -> ${b.publish_cycle_minutes}`);
      if (a.publish_mode !== b.publish_mode) lines.push(`모드: ${a.publish_mode} -> ${b.publish_mode}`);
      if (a.publish_format !== b.publish_format) lines.push(`형식: ${a.publish_format} -> ${b.publish_format}`);
      if (a.writing_style !== b.writing_style) lines.push(`작성형식: ${a.writing_style} -> ${b.writing_style}`);
      if (a.api_url !== b.api_url) lines.push(`API URL: ${a.api_url || "(비어있음)"} -> ${b.api_url || "(비어있음)"}`);
      return lines;
    }

    function refreshPublishSettingDiffHint() {
      const hint = qs("#publishSettingDiffHint");
      if (!hint) return;
      const code = String(qs("#publishSettingChannel")?.value || "");
      if (!code) {
        hint.textContent = "변경사항 없음";
        return;
      }
      const prev = state.publishSettingSnapshotByCode[code] || {};
      const next = currentPublishSettingFormPayload();
      const lines = publishSettingDiffLines(prev, next);
      hint.textContent = lines.length ? `변경 예정: ${lines.join(", ")}` : "변경사항 없음";
    }

    function getSortedPublishSettingRows(rows, channelByCode) {
      const list = Array.isArray(rows) ? [...rows] : [];
      const search = String(state.publishSettingSearch || "").trim().toLowerCase();
      let filtered = list;
      if (search) {
        filtered = list.filter((row) => {
          const channel = channelByCode[String(row.channel_code || "")] || {};
          const hay = `${row.channel_code || ""} ${channel.display_name || ""}`.toLowerCase();
          return hay.includes(search);
        });
      }
      const mode = String(state.publishSettingSort || "name_asc");
      if (mode === "enabled_first") {
        return filtered.sort((a, b) => {
          const ea = Number(!!(channelByCode[String(a.channel_code || "")] || {}).is_enabled);
          const eb = Number(!!(channelByCode[String(b.channel_code || "")] || {}).is_enabled);
          if (ea !== eb) return eb - ea;
          return String((channelByCode[String(a.channel_code || "")] || {}).display_name || a.channel_code || "").localeCompare(String((channelByCode[String(b.channel_code || "")] || {}).display_name || b.channel_code || ""), "ko");
        });
      }
      if (mode === "cycle_asc") {
        return filtered.sort((a, b) => Number(a.publish_cycle_minutes || 60) - Number(b.publish_cycle_minutes || 60));
      }
      return filtered.sort((a, b) => String((channelByCode[String(a.channel_code || "")] || {}).display_name || a.channel_code || "").localeCompare(String((channelByCode[String(b.channel_code || "")] || {}).display_name || b.channel_code || ""), "ko"));
    }

    async function refreshPublishSettingsSection() {
      const [s, channelsRaw, channelSettingsRaw] = await Promise.all([
        request("/api/v2/settings/publish"),
        request("/api/publish-channels"),
        request("/api/publish-channel-settings"),
      ]);
      const channels = Array.isArray(channelsRaw) ? channelsRaw : [];
      const channelSettings = Array.isArray(channelSettingsRaw) ? channelSettingsRaw : [];
      qs("#publishSettingModeV2").value = s.channel_mode || "semi_auto";
      qs("#publishSettingCycleV2").value = s.cycle_minutes || 60;
      qs("#publishSettingRetryV2").value = s.retry_count || 1;
      qs("#publishSettingRequireApproval").checked = !!s.require_approval;

      const channelByCode = {};
      (channels || []).forEach((c) => {
        channelByCode[String(c.code || "")] = c;
      });
      const settingByCode = {};
      channelSettings.forEach((row) => {
        settingByCode[String(row.channel_code || "")] = row;
        state.publishSettingSnapshotByCode[String(row.channel_code || "")] = normalizePublishSettingSnapshot(row);
      });

      const cardList = qs("#publishSettingCardList");
      if (cardList) {
        cardList.innerHTML = "";
        const sortedRows = getSortedPublishSettingRows(channelSettings, channelByCode);
        if (!sortedRows.length) {
          cardList.innerHTML = "<div class='manage-card-empty'>설정 없음</div>";
        } else {
          sortedRows.forEach((row) => {
            const code = String(row.channel_code || "");
            const channel = channelByCode[code] || {};
            const enabled = !!channel.is_enabled;
            const selected = state.selectedPublishSettingChannelCode && String(state.selectedPublishSettingChannelCode) === code;
            const card = document.createElement("button");
            card.type = "button";
            card.className = `manage-card${selected ? " selected" : ""}`;
            card.innerHTML = `
              <div class="manage-card-head">
                <div class="manage-card-title">${escapeHtml(channel.display_name || code || "-")}</div>
                <span class="badge-status ${enabled ? "ok" : "neutral"}">${enabled ? "활성" : "비활성"}</span>
              </div>
              <div class="manage-card-sub">${escapeHtml(code || "-")}</div>
              <div class="manage-card-meta">
                <span class="badge-channel">${escapeHtml(publishModeLabel(row.publish_mode))}</span>
                <span class="badge-channel">${escapeHtml(publishFormatLabel(row.publish_format))}</span>
                <span class="badge-channel">${escapeHtml(publishStyleLabel(row.writing_style))}</span>
                <span class="badge-channel">${escapeHtml(`${row.publish_cycle_minutes || 60}분`)}</span>
              </div>
            `;
            card.addEventListener("click", () => {
              state.selectedPublishChannelId = channel.id || null;
              state.selectedPublishSettingChannelCode = code;
              qsa("#publishSettingCardList .manage-card").forEach((el) => el.classList.remove("selected"));
              card.classList.add("selected");
              if (qs("#publishSettingChannel")) qs("#publishSettingChannel").value = code;
              if (qs("#publishSettingApi")) qs("#publishSettingApi").value = row.api_url || "";
              if (qs("#publishSettingCycle")) qs("#publishSettingCycle").value = row.publish_cycle_minutes || 60;
              if (qs("#publishSettingMode")) qs("#publishSettingMode").value = row.publish_mode || "semi_auto";
              if (qs("#publishSettingFormat")) qs("#publishSettingFormat").value = row.publish_format || "blog";
              if (qs("#publishSettingStyle")) qs("#publishSettingStyle").value = row.writing_style || "informative";
              refreshPublishSettingDiffHint();
            });
            cardList.appendChild(card);
          });
        }
      }

      const sel = qs("#publishSettingChannel");
      if (sel) {
        const prev = String(sel.value || state.selectedPublishSettingChannelCode || "");
        sel.innerHTML = "";
        channels.forEach((c) => {
          const o = document.createElement("option");
          o.value = c.code;
          o.textContent = `${c.display_name} (${c.code})${c.is_enabled ? "" : " [비활성]"}`;
          sel.appendChild(o);
        });
        if (!selectValueIfExists(sel, prev) && sel.options.length) {
          sel.value = sel.options[0].value;
        }
        const selectedCode = String(sel.value || "");
        const selectedSetting = settingByCode[selectedCode];
        const selectedChannel = channelByCode[selectedCode] || {};
        state.selectedPublishSettingChannelCode = selectedCode || null;
        state.selectedPublishChannelId = selectedChannel.id || null;
        if (selectedSetting) {
          if (qs("#publishSettingApi")) qs("#publishSettingApi").value = selectedSetting.api_url || "";
          if (qs("#publishSettingCycle")) qs("#publishSettingCycle").value = selectedSetting.publish_cycle_minutes || 60;
          if (qs("#publishSettingMode")) qs("#publishSettingMode").value = selectedSetting.publish_mode || "semi_auto";
          if (qs("#publishSettingFormat")) qs("#publishSettingFormat").value = selectedSetting.publish_format || "blog";
          if (qs("#publishSettingStyle")) qs("#publishSettingStyle").value = selectedSetting.writing_style || "informative";
        }
        refreshPublishSettingDiffHint();
      }
    }

    async function savePublishSettingsSection() {
      await request("/api/v2/settings/publish", {
        method: "POST",
        body: JSON.stringify({
          channel_mode: qs("#publishSettingModeV2").value || "semi_auto",
          cycle_minutes: Number(qs("#publishSettingCycleV2").value || 60),
          retry_count: Number(qs("#publishSettingRetryV2").value || 1),
          require_approval: !!qs("#publishSettingRequireApproval").checked,
        }),
      });
    }

    async function savePublishChannelSetting() {
      const fieldMap = {
        channel_code: "#publishSettingChannel",
        publish_mode: "#publishSettingMode",
        publish_format: "#publishSettingFormat",
        writing_style: "#publishSettingStyle",
        api_url: "#publishSettingApi",
      };
      clearFieldErrors(Object.values(fieldMap));
      applyFieldErrors({}, fieldMap, "#publishSettingValidationHint");
      const payload = currentPublishSettingFormPayload();
      if (!payload.channel_code) throw new Error("대상 채널을 선택하세요.");
      const prev = state.publishSettingSnapshotByCode[payload.channel_code] || {};
      const diff = publishSettingDiffLines(prev, payload);
      if (!diff.length) {
        showAlert("변경사항이 없습니다.", "안내", "warn");
        return;
      }
      const ok = await showConfirm(`아래 변경사항으로 저장할까요?\n${diff.join("\n")}`, "저장 확인", "warn");
      if (!ok) return;
      try {
        await request("/api/publish-channel-settings/save", { method: "POST", body: JSON.stringify(payload) });
      } catch (err) {
        applyFieldErrors(err?.fields, fieldMap, "#publishSettingValidationHint");
        throw err;
      }
      state.publishSettingSnapshotByCode[payload.channel_code] = normalizePublishSettingSnapshot(payload);
      refreshPublishSettingDiffHint();
      applyFieldErrors({}, fieldMap, "#publishSettingValidationHint");
    }

    async function testPublishSettingApiUrl() {
      const channelCode = String(qs("#publishSettingChannel")?.value || "").trim();
      const apiUrl = String(qs("#publishSettingApi")?.value || "").trim();
      if (!channelCode) throw new Error("대상 채널을 선택하세요.");
      if (!apiUrl) throw new Error("API URL을 입력하세요.");
      const result = await request("/api/publish-channel-settings/test-url", {
        method: "POST",
        body: JSON.stringify({ channel_code: channelCode, api_url: apiUrl }),
      });
      const ok = !!result.ok;
      showAlert(`테스트 결과: ${ok ? "성공" : "실패"}\n코드: ${result.status_code || "-"}\n${result.message || ""}`, "API URL 테스트", ok ? "success" : "warn");
    }

    return {
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
    };
  }

  window.createPublishSettingsModule = createPublishSettingsModule;
})();
