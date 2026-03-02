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
      return {
        method: String(qs("#labelSettingMethod")?.value || "rule"),
        batch_size: clampInt(qs("#labelSettingBatch")?.value || 300, 10, 1000, 300),
        quality_threshold: clampInt(qs("#labelSettingQuality")?.value || 3, 1, 5, 3),
        relabel_policy: String(qs("#labelSettingPolicy")?.value || "skip"),
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
      if (qs("#labelSettingMethod")) qs("#labelSettingMethod").value = payload.method || "rule";
      if (qs("#labelSettingBatch")) qs("#labelSettingBatch").value = String(payload.batch_size || 300);
      if (qs("#labelSettingQuality")) qs("#labelSettingQuality").value = String(payload.quality_threshold || 3);
      if (qs("#labelSettingPolicy")) qs("#labelSettingPolicy").value = payload.relabel_policy || "skip";
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
      if (!hintMode && !hintQuality) return;
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
      const data = stat && stat.ok ? (stat.data || {}) : {};
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
    }

    return {
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
    };
  }

  window.createLabelingModule = createLabelingModule;
})();
