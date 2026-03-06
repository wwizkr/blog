(() => {
  function createLabelingModule(ctx) {
    const { qs, state, request, safeRequest, appendLog, showAlert, clampInt } = ctx || {};

    function labelingPresetValues(name) {
      const key = String(name || "default").toLowerCase();
      if (key === "strict") {
        return { method: "ai", batch_size: 120, quality_threshold: 5, relabel_policy: "skip" };
      }
      if (key === "aggressive" || key === "fast") {
        return { method: "ai", batch_size: 500, quality_threshold: 2, relabel_policy: "overwrite" };
      }
      return { method: "rule", batch_size: 300, quality_threshold: 3, relabel_policy: "skip" };
    }

    function labelSettingDraft() {
      const thresholdMid = clampInt(qs("#labelSettingThresholdMid")?.value || 3, 1, 5, 3);
      const thresholdHighRaw = clampInt(qs("#labelSettingThresholdHigh")?.value || 4, 1, 5, 4);
      return {
        method: String(qs("#labelSettingMethod")?.value || "rule"),
        batch_size: clampInt(qs("#labelSettingBatch")?.value || 300, 10, 1000, 300),
        quality_threshold: clampInt(qs("#labelSettingQuality")?.value || 3, 1, 5, 3),
        relabel_policy: String(qs("#labelSettingPolicy")?.value || "skip"),
        auto_enabled: !!qs("#labelSettingAutoEnabled")?.checked,
        interval_minutes: clampInt(qs("#labelSettingInterval")?.value || 15, 5, 1440, 15),
        free_api_daily_limit: clampInt(qs("#labelSettingFreeLimit")?.value || 200, 0, 100000, 200),
        paid_api_daily_limit: clampInt(qs("#labelSettingPaidLimit")?.value || 20, 0, 100000, 20),
        threshold_mid: thresholdMid,
        threshold_high: Math.max(thresholdMid, thresholdHighRaw),
      };
    }

    function syncLabelSettingModeUi() {
      const method = String(qs("#labelSettingMethod")?.value || "rule");
      const policy = qs("#labelSettingPolicy");
      if (policy) {
        policy.disabled = method !== "ai";
        policy.title = method === "ai" ? "" : "rule 방식에서는 재라벨링 정책이 사용되지 않습니다.";
      }
    }

    function applyLabelSettingToForm(payload) {
      const batchSize = Number.isFinite(Number(payload.batch_size)) ? Number(payload.batch_size) : 300;
      const qualityThreshold = Number.isFinite(Number(payload.quality_threshold)) ? Number(payload.quality_threshold) : 3;
      const intervalMinutes = Number.isFinite(Number(payload.interval_minutes)) ? Number(payload.interval_minutes) : 15;
      const freeLimit = Number.isFinite(Number(payload.free_api_daily_limit)) ? Number(payload.free_api_daily_limit) : 200;
      const paidLimit = Number.isFinite(Number(payload.paid_api_daily_limit)) ? Number(payload.paid_api_daily_limit) : 20;
      const thresholdMid = Number.isFinite(Number(payload.threshold_mid)) ? Number(payload.threshold_mid) : 3;
      const thresholdHigh = Number.isFinite(Number(payload.threshold_high)) ? Number(payload.threshold_high) : 4;
      if (qs("#labelSettingMethod")) qs("#labelSettingMethod").value = payload.method || "rule";
      if (qs("#labelSettingBatch")) qs("#labelSettingBatch").value = String(batchSize);
      if (qs("#labelSettingQuality")) qs("#labelSettingQuality").value = String(qualityThreshold);
      if (qs("#labelSettingPolicy")) qs("#labelSettingPolicy").value = payload.relabel_policy || "skip";
      if (qs("#labelSettingAutoEnabled")) qs("#labelSettingAutoEnabled").checked = !!payload.auto_enabled;
      if (qs("#labelSettingInterval")) qs("#labelSettingInterval").value = String(intervalMinutes);
      if (qs("#labelSettingFreeLimit")) qs("#labelSettingFreeLimit").value = String(freeLimit);
      if (qs("#labelSettingPaidLimit")) qs("#labelSettingPaidLimit").value = String(paidLimit);
      if (qs("#labelSettingThresholdMid")) qs("#labelSettingThresholdMid").value = String(thresholdMid);
      if (qs("#labelSettingThresholdHigh")) qs("#labelSettingThresholdHigh").value = String(thresholdHigh);
      syncLabelSettingModeUi();
    }

    function updateRetryLabelingButton() {
      const btn = qs("#retryFailedLabelingBtn");
      if (!btn) return;
      const stage = String(state.labelLastFailedStage || "");
      btn.disabled = !stage;
      if (stage === "content") btn.textContent = "실패 재시도(텍스트)";
      else if (stage === "image") btn.textContent = "실패 재시도(이미지)";
      else btn.textContent = "실패 재시도";
    }

    async function refreshLabelSettingHints(stats) {
      const hintMode = qs("#labelSettingModeHint");
      const hintQuality = qs("#labelSettingQualityHint");
      const hintAuto = qs("#labelSettingAutoHint");
      if (!hintMode && !hintQuality && !hintAuto) return;
      const cfg = labelSettingDraft();
      const modeText = cfg.method === "ai"
        ? "AI 방식: 고품질 라벨링, 처리속도/비용 영향이 큽니다."
        : "Rule 방식: 빠르고 안정적이지만 표현 다양성은 낮습니다.";
      if (hintMode) {
        const policyText = cfg.method === "ai"
          ? (cfg.relabel_policy === "overwrite" ? "재라벨링: overwrite(기존 라벨 갱신)" : "재라벨링: skip(기존 라벨 유지)")
          : "재라벨링 정책은 AI 모드에서만 적용됩니다.";
        hintMode.textContent = `${modeText} | 배치 ${cfg.batch_size}건`;
        hintMode.textContent = `${hintMode.textContent} | ${policyText}`;
      }

      const stat = stats || await safeRequest("/api/labeling/stats");
      const [autoStatusRes, settingRes] = await Promise.all([
        safeRequest("/api/labeling/auto/status"),
        safeRequest("/api/v2/settings/label"),
      ]);
      const data = stat && stat.ok ? (stat.data || {}) : {};
      const auto = autoStatusRes && autoStatusRes.ok ? (autoStatusRes.data || {}) : {};
      const setting = settingRes && settingRes.ok ? (settingRes.data || {}) : {};
      const contentTotal = Number(data.contents_total || 0);
      const contentLabeled = Number(data.contents_labeled || 0);
      const imageTotal = Number(data.images_total || 0);
      const imageLabeled = Number(data.images_labeled || 0);
      const remaining = Math.max(0, contentTotal - contentLabeled) + Math.max(0, imageTotal - imageLabeled);
      const batchNeed = cfg.batch_size > 0 ? Math.ceil(remaining / cfg.batch_size) : 0;
      const impact = cfg.quality_threshold >= 5
        ? "엄격: 정확도 상승, 통과량 감소"
        : cfg.quality_threshold <= 2
          ? "완화: 처리량 증가, 품질 편차 증가"
          : "균형: 처리량/품질 균형";
      if (hintQuality) hintQuality.textContent = `품질 임계값 ${cfg.quality_threshold} (${impact}) | 예상 남은 배치 ${batchNeed}회`;
      if (hintAuto) {
        const autoMode = cfg.auto_enabled ? "ON" : "OFF";
        hintAuto.textContent = `자동 실행 ${autoMode} | 주기 ${cfg.interval_minutes}분 | 다음 실행 ${auto.next_run_at || "-"} | 최근 처리 텍스트 ${Number(auto.last_content_processed || 0)} / 이미지 ${Number(auto.last_image_processed || 0)} | Free ${Number(setting.free_api_used_today || 0)}/${Number(setting.free_api_daily_limit || cfg.free_api_daily_limit)} | Paid ${Number(setting.paid_api_used_today || 0)}/${Number(setting.paid_api_daily_limit || cfg.paid_api_daily_limit)}`;
      }
    }

    async function refreshLabelingRunLogs() {
      const tbody = qs("#labelingLogTable tbody");
      if (!tbody) return;
      const res = await safeRequest("/api/labeling/runs?limit=30");
      const rows = Array.isArray(res?.data) ? res.data : [];
      tbody.innerHTML = rows.length ? "" : "<tr><td>실행 이력 없음</td></tr>";
      rows.forEach((row) => {
        const tr = document.createElement("tr");
        const stage = row.stage_summary && typeof row.stage_summary === "object" ? row.stage_summary : {};
        const stageText = [
          `rule:${Number(stage.rule_done || 0)}`,
          `free:${Number(stage.free_api_done || 0)}`,
          `paid:${Number(stage.paid_api_done || 0)}`,
        ].join(" / ");
        tr.innerHTML = `<td>[${row.created_at || "-"}] ${row.run_kind || "-"} ${row.method || "-"} | ${Number(row.labeled_count || 0)}/${Number(row.target_count || 0)} | quota free+${Number(row.free_api_used || 0)} paid+${Number(row.paid_api_used || 0)} | ${stageText} | ${row.message || "-"}</td>`;
        tbody.appendChild(tr);
      });
    }

    async function refreshLabelingSection() {
      const [s, cfgRes] = await Promise.all([
        request("/api/labeling/stats"),
        safeRequest("/api/v2/settings/label"),
      ]);
      const contentTotal = Number(s.contents_total || 0);
      const contentLabeled = Number(s.contents_labeled || 0);
      const imageTotal = Number(s.images_total || 0);
      const imageLabeled = Number(s.images_labeled || 0);
      const contentRemain = Math.max(0, contentTotal - contentLabeled);
      const imageRemain = Math.max(0, imageTotal - imageLabeled);
      const total = contentTotal + imageTotal;
      const labeled = contentLabeled + imageLabeled;
      const pct = total ? ((labeled / total) * 100).toFixed(1) : "100.0";
      const statsNode = qs("#labelingStats");
      if (statsNode) {
        statsNode.textContent = `완료율 ${pct}% | 콘텐츠: ${contentLabeled}/${contentTotal} | 이미지: ${imageLabeled}/${imageTotal}`;
      }
      const queueNode = qs("#labelingQueueHint");
      const cfg = cfgRes.ok && cfgRes.data && typeof cfgRes.data === "object" ? cfgRes.data : {};
      const batchSize = clampInt(cfg.batch_size || qs("#labelSettingBatch")?.value || 300, 10, 1000, 300);
      const contentRounds = Math.ceil(contentRemain / batchSize);
      const imageRounds = Math.ceil(imageRemain / batchSize);
      if (queueNode) {
        queueNode.textContent = `대기 큐 | 콘텐츠 ${contentRemain}건(${contentRounds}회) / 이미지 ${imageRemain}건(${imageRounds}회)`;
      }
      updateRetryLabelingButton();
      await refreshLabelSettingHints({ ok: true, data: s });
      await refreshLabelingRunLogs();
    }

    function stopLabelingPolling() {
      if (!state.labelPollTimer) return;
      clearInterval(state.labelPollTimer);
      state.labelPollTimer = null;
      state.labelPollingInFlight = false;
    }

    function startLabelingPolling() {
      stopLabelingPolling();
      state.labelPollTimer = setInterval(async () => {
        if (state.labelPollingInFlight) return;
        state.labelPollingInFlight = true;
        try {
          await refreshLabelingSection();
        } catch (_e) {
          // keep interval alive
        } finally {
          state.labelPollingInFlight = false;
        }
      }, 10000);
    }

    async function runLabelingStage(stage) {
      const kind = stage === "image" ? "image" : "content";
      const endpoint = kind === "image" ? "/api/labeling/run-image" : "/api/labeling/run-content";
      const label = kind === "image" ? "이미지" : "텍스트";
      try {
        const r = await request(endpoint, { method: "POST", body: "{}" });
        appendLog("labelingLogTable", `${label} 라벨링 완료: ${r.labeled}/${r.target}`);
        state.labelLastFailedStage = "";
        updateRetryLabelingButton();
        await refreshLabelingSection();
        return r;
      } catch (e) {
        state.labelLastFailedStage = kind;
        updateRetryLabelingButton();
        appendLog("labelingLogTable", `${label} 라벨링 실패: ${String(e)}`);
        throw e;
      }
    }

    async function retryFailedLabelingRun() {
      const stage = String(state.labelLastFailedStage || "");
      if (!stage) {
        showAlert("재시도할 실패 작업이 없습니다.", "안내", "warn");
        return;
      }
      await runLabelingStage(stage);
    }

    async function refreshLabelSettingsSection() {
      const s = await request("/api/v2/settings/label");
      applyLabelSettingToForm({
        method: s.method || "rule",
        batch_size: s.batch_size || 300,
        quality_threshold: s.quality_threshold || 3,
        relabel_policy: s.relabel_policy || "skip",
        auto_enabled: !!s.auto_enabled,
        interval_minutes: s.interval_minutes || 15,
        free_api_daily_limit: s.free_api_daily_limit || 200,
        paid_api_daily_limit: s.paid_api_daily_limit || 20,
        threshold_mid: s.threshold_mid || 3,
        threshold_high: s.threshold_high || 4,
      });
      const presetNode = qs("#labelSettingPreset");
      if (presetNode) {
        const strict = labelingPresetValues("strict");
        const aggressive = labelingPresetValues("aggressive");
        const now = labelSettingDraft();
        if (now.method === strict.method && now.batch_size === strict.batch_size && now.quality_threshold === strict.quality_threshold && now.relabel_policy === strict.relabel_policy) {
          presetNode.value = "strict";
        } else if (now.method === aggressive.method && now.batch_size === aggressive.batch_size && now.quality_threshold === aggressive.quality_threshold && now.relabel_policy === aggressive.relabel_policy) {
          presetNode.value = "aggressive";
        } else {
          presetNode.value = "default";
        }
      }
      await refreshLabelSettingHints();
    }

    async function saveLabelSettingsSection() {
      const payload = labelSettingDraft();
      await request("/api/v2/settings/label", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      await refreshLabelingSection();
      await refreshLabelSettingsSection();
    }

    async function tickAutoLabeling() {
      await request("/api/labeling/auto/tick", { method: "POST", body: "{}" });
      await refreshLabelingSection();
      await refreshLabelSettingHints();
    }

    return {
      labelingPresetValues,
      labelSettingDraft,
      applyLabelSettingToForm,
      syncLabelSettingModeUi,
      updateRetryLabelingButton,
        refreshLabelSettingHints,
        refreshLabelingRunLogs,
        refreshLabelingSection,
      stopLabelingPolling,
      startLabelingPolling,
      runLabelingStage,
      retryFailedLabelingRun,
      refreshLabelSettingsSection,
      saveLabelSettingsSection,
      tickAutoLabeling,
    };
  }

  window.createLabelingModule = createLabelingModule;
})();
