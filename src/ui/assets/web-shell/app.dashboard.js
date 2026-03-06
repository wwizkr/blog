(() => {
  function createDashboardModule(ctx) {
    const {
      qs,
      state,
      fmt,
      safeRequest,
      navigateToNode,
      DASHBOARD_PREF_STORAGE_KEY,
      DASHBOARD_HISTORY_STORAGE_KEY,
    } = ctx || {};

    function renderAutomationStatus(status) {
      const collect = status?.collect || {};
      const labeling = status?.labeling || {};
      const writer = status?.writer || {};
      const publish = status?.publish || {};
      const writerChannels = Array.isArray(writer.channels) ? writer.channels : [];
      const writerAutoChannels = writerChannels.filter((r) => !!r.auto_enabled);
      const writerNextRun = writerAutoChannels.length
        ? writerAutoChannels
          .map((r) => String(r.next_run_at || ""))
          .filter(Boolean)
          .sort()[0]
        : "";

      const collectErr = String(collect.last_error || "").trim();
      const labelingErr = String(labeling.last_error || "").trim();
      const writerErr = String(writer.last_error || "").trim();
      const publishLogs = Array.isArray(publish.logs) ? publish.logs : [];
      const publishErr = [...publishLogs].reverse().find((line) => /(실패|오류|error)/i.test(String(line || ""))) || "";

      const collectState = collectErr
        ? "error"
        : (collect.running ? "running" : (collect.worker_started ? "waiting" : "stopped"));
      const writerState = writerErr
        ? "error"
        : (writer.running ? "running" : (writer.worker_started ? "waiting" : "stopped"));
      const labelingState = labelingErr
        ? "error"
        : (labeling.running ? "running" : (labeling.auto_enabled ? "waiting" : "stopped"));
      const publishState = publishErr
        ? "error"
        : (publish.enabled ? (publish.pause_until ? "waiting" : "running") : "stopped");

      const stateLabel = (v) => (v === "running" ? "실행중" : (v === "waiting" ? "대기중" : (v === "error" ? "오류" : "중지")));
      const stateLevel = (v) => (v === "running" ? "ok" : (v === "waiting" ? "neutral" : (v === "error" ? "error" : "warn")));

      const createStatePill = (s, label) => {
        const pill = document.createElement("span");
        pill.className = `auto-status-pill state-${s || "stopped"}`;
        const dot = document.createElement("span");
        dot.className = "state-dot";
        const txt = document.createElement("span");
        txt.textContent = label;
        pill.appendChild(dot);
        pill.appendChild(txt);
        return pill;
      };

      const setBadge = (selector, title, s, detail) => {
        const node = qs(selector);
        if (!node) return;
        node.classList.add("auto-badge");
        node.classList.remove("badge-ok", "badge-warn", "badge-neutral", "badge-error");
        node.classList.add(`badge-${stateLevel(s)}`);
        node.innerHTML = "";
        const titleNode = document.createElement("span");
        titleNode.className = "auto-badge-title";
        titleNode.textContent = title;
        node.appendChild(titleNode);
        node.appendChild(createStatePill(s, stateLabel(s)));
        if (detail) {
          const detailNode = document.createElement("span");
          detailNode.className = "auto-badge-detail";
          detailNode.textContent = detail;
          node.appendChild(detailNode);
        }
      };

      setBadge("#collectAutoBadge", "수집 자동", collectState, collectState === "waiting" ? `${collect.interval_minutes || "-"}분` : "");
      setBadge("#labelAutoBadge", "라벨 자동", labelingState, labelingState === "waiting" ? `${labeling.interval_minutes || "-"}분` : "");
      setBadge("#writerAutoBadge", "작성 자동", writerState, writerState === "waiting" ? `${writer.auto_channel_count || 0}채널` : "");
      setBadge("#publishAutoBadge", "발행 자동", publishState, publish.pause_until ? fmt(publish.pause_until) : "");

      const setHint = (selector, title, s, details) => {
        const node = qs(selector);
        if (!node) return;
        node.classList.add("auto-status-hint");
        node.innerHTML = "";
        const titleNode = document.createElement("span");
        titleNode.className = "auto-status-title";
        titleNode.textContent = title;
        node.appendChild(titleNode);
        node.appendChild(createStatePill(s, stateLabel(s)));
        const detailText = details.filter(Boolean).join(" | ");
        if (detailText) {
          const detailNode = document.createElement("span");
          detailNode.className = "auto-status-detail";
          detailNode.textContent = ` | ${detailText}`;
          node.appendChild(detailNode);
        }
      };

      setHint("#collectAutoStatusHint", "자동 수집 상태", collectState, [
        `다음 실행 ${fmt(collect.next_run_at)}`,
        `최근 완료 ${fmt(collect.last_finished_at)}`,
        collectErr ? `오류: ${collectErr}` : "",
      ]);

      setHint("#writerAutoStatusHint", "자동 작성 상태", writerState, [
        `다음 실행 ${fmt(writerNextRun)}`,
        `최근 처리 ${Number(writer.last_tick_processed || 0)}건`,
        writerErr ? `오류: ${writerErr}` : "",
      ]);

      setHint("#labelingAutoStatusHint", "자동 라벨링 상태", labelingState, [
        `다음 실행 ${fmt(labeling.next_run_at)}`,
        `최근 처리 텍스트 ${Number(labeling.last_content_processed || 0)}건 / 이미지 ${Number(labeling.last_image_processed || 0)}건`,
        labelingErr ? `오류: ${labelingErr}` : "",
      ]);

      setHint("#publishAutoStatusHint", "자동 발행 상태", publishState, [
        publish.pause_until ? `일시중지 ${fmt(publish.pause_until)}` : "",
        `대상 채널 ${Array.isArray(publish.channels) ? publish.channels.length : 0}개`,
        publishErr ? `오류: ${publishErr}` : "",
      ]);
    }

    async function refreshAutomationStatus() {
      const res = await safeRequest("/api/automation/status");
      if (!res.ok || !res.data) return;
      state.automationStatus = res.data;
      renderAutomationStatus(res.data);
    }

    function startAutomationPolling() {
      if (state.automationPollTimer) clearInterval(state.automationPollTimer);
      state.automationPollTimer = setInterval(() => {
        refreshAutomationStatus().catch(() => {});
      }, 5000);
    }

    function dashboardReadPrefs() {
      try {
        const raw = localStorage.getItem(DASHBOARD_PREF_STORAGE_KEY);
        const parsed = raw ? JSON.parse(raw) : {};
        if (!parsed || typeof parsed !== "object") return;
        state.dashboardAutoRefreshEnabled = !!parsed.auto_refresh_enabled;
        const sec = Number(parsed.auto_refresh_sec || 30);
        state.dashboardAutoRefreshSec = Math.max(5, Math.min(300, Number.isFinite(sec) ? sec : 30));
        const t = parsed.thresholds && typeof parsed.thresholds === "object" ? parsed.thresholds : {};
        state.dashboardThresholds = {
          collect_fail: Math.max(1, Math.min(100, Number(t.collect_fail || 20) || 20)),
          writer_unready: Math.max(1, Math.min(100, Number(t.writer_unready || 30) || 30)),
          publish_fail: Math.max(1, Math.min(100, Number(t.publish_fail || 20) || 20)),
          monitor_errors: Math.max(1, Math.min(999, Number(t.monitor_errors || 5) || 5)),
        };
      } catch (_e) {
        // ignore
      }

      try {
        const rawHistory = localStorage.getItem(DASHBOARD_HISTORY_STORAGE_KEY);
        const parsedHistory = rawHistory ? JSON.parse(rawHistory) : {};
        state.dashboardHistory = parsedHistory && typeof parsedHistory === "object" ? parsedHistory : {};
      } catch (_e) {
        state.dashboardHistory = {};
      }
    }

    function dashboardWritePrefs() {
      try {
        localStorage.setItem(DASHBOARD_PREF_STORAGE_KEY, JSON.stringify({
          auto_refresh_enabled: !!state.dashboardAutoRefreshEnabled,
          auto_refresh_sec: Number(state.dashboardAutoRefreshSec || 30),
          thresholds: { ...(state.dashboardThresholds || {}) },
        }));
        localStorage.setItem(DASHBOARD_HISTORY_STORAGE_KEY, JSON.stringify(state.dashboardHistory || {}));
      } catch (_e) {
        // ignore
      }
    }

    function dashboardBindControls() {
      const auto = qs("#dashboardAutoRefreshEnabled");
      const sec = qs("#dashboardAutoRefreshSec");
      const collectFail = qs("#dashboardWarnCollectFail");
      const writerUnready = qs("#dashboardWarnWriterUnready");
      const publishFail = qs("#dashboardWarnPublishFail");
      const monitorErrors = qs("#dashboardWarnMonitorErrors");

      if (auto) auto.checked = !!state.dashboardAutoRefreshEnabled;
      if (sec) sec.value = String(state.dashboardAutoRefreshSec || 30);
      if (collectFail) collectFail.value = String(state.dashboardThresholds.collect_fail || 20);
      if (writerUnready) writerUnready.value = String(state.dashboardThresholds.writer_unready || 30);
      if (publishFail) publishFail.value = String(state.dashboardThresholds.publish_fail || 20);
      if (monitorErrors) monitorErrors.value = String(state.dashboardThresholds.monitor_errors || 5);
    }

    function dashboardApplyControlValues() {
      const auto = qs("#dashboardAutoRefreshEnabled");
      const sec = qs("#dashboardAutoRefreshSec");
      const collectFail = qs("#dashboardWarnCollectFail");
      const writerUnready = qs("#dashboardWarnWriterUnready");
      const publishFail = qs("#dashboardWarnPublishFail");
      const monitorErrors = qs("#dashboardWarnMonitorErrors");

      state.dashboardAutoRefreshEnabled = !!auto?.checked;
      state.dashboardAutoRefreshSec = Math.max(5, Math.min(300, Number(sec?.value || 30) || 30));
      state.dashboardThresholds.collect_fail = Math.max(1, Math.min(100, Number(collectFail?.value || 20) || 20));
      state.dashboardThresholds.writer_unready = Math.max(1, Math.min(100, Number(writerUnready?.value || 30) || 30));
      state.dashboardThresholds.publish_fail = Math.max(1, Math.min(100, Number(publishFail?.value || 20) || 20));
      state.dashboardThresholds.monitor_errors = Math.max(1, Math.min(999, Number(monitorErrors?.value || 5) || 5));
      dashboardWritePrefs();
    }

    function stopDashboardPolling() {
      if (!state.dashboardPollTimer) return;
      clearInterval(state.dashboardPollTimer);
      state.dashboardPollTimer = null;
    }

    function startDashboardPolling() {
      stopDashboardPolling();
      if (!state.dashboardAutoRefreshEnabled) return;
      const ms = Math.max(5, Number(state.dashboardAutoRefreshSec || 30)) * 1000;
      state.dashboardPollTimer = setInterval(() => {
        refreshDashboardSection().catch(() => {});
      }, ms);
    }

    function dashboardSparkline(values) {
      const data = Array.isArray(values) ? values.filter((v) => Number.isFinite(Number(v))).map((v) => Number(v)) : [];
      if (!data.length) return "-";
      const min = Math.min(...data);
      const max = Math.max(...data);
      const blocks = "▁▂▃▄▅▆▇█";
      if (max === min) return blocks[Math.min(blocks.length - 1, Math.max(0, Math.round(max / 15)))]?.repeat(Math.min(20, data.length)) || "▁";
      return data.map((v) => {
        const norm = (v - min) / (max - min);
        const idx = Math.max(0, Math.min(blocks.length - 1, Math.round(norm * (blocks.length - 1))));
        return blocks[idx];
      }).join("");
    }

    function dashboardPushHistory(key, value) {
      const bucket = Array.isArray(state.dashboardHistory[key]) ? state.dashboardHistory[key] : [];
      bucket.push(Number.isFinite(Number(value)) ? Number(value) : 0);
      state.dashboardHistory[key] = bucket.slice(-20);
    }

    async function refreshDashboardSection() {
      dashboardApplyControlValues();
      const autoWrap = qs("#dashboardAutoGrid");
      const opsWrap = qs("#dashboardOpsGrid");
      const labelingWrap = qs("#dashboardLabelingGrid");
      const labelingHint = qs("#dashboardLabelingHint");
      const resourceWrap = qs("#dashboardResourceGrid");
      const hint = qs("#dashboardHint");
      if (!autoWrap || !opsWrap || !resourceWrap || !labelingWrap) return;

      const [
        summaryRes,
        collectJobsRes,
        labelStatsRes,
        labelSnapshotRes,
        labelSettingRes,
        writerRes,
        publishAutoRes,
        monitorRes,
        collectStatusRes,
        writerStatusRes,
        automationRes,
      ] = await Promise.all([
        safeRequest("/api/dashboard/summary"),
        safeRequest("/api/collect/jobs"),
        safeRequest("/api/labeling/stats"),
        safeRequest("/api/labeling/automation-snapshot"),
        safeRequest("/api/v2/settings/label"),
        safeRequest("/api/writer/run-summary"),
        safeRequest("/api/publish/auto/status"),
        safeRequest("/api/v2/monitor/events?limit=200"),
        safeRequest("/api/collect/status"),
        safeRequest("/api/writer/status"),
        safeRequest("/api/automation/status"),
      ]);

      const summary = summaryRes.ok && summaryRes.data && typeof summaryRes.data === "object" ? summaryRes.data : {};
      const collectJobs = Array.isArray(collectJobsRes.data) ? collectJobsRes.data : [];
      const labelStats = labelStatsRes.ok && labelStatsRes.data && typeof labelStatsRes.data === "object" ? labelStatsRes.data : {};
      const labelSnapshot = labelSnapshotRes.ok && labelSnapshotRes.data && typeof labelSnapshotRes.data === "object" ? labelSnapshotRes.data : {};
      const labelSetting = labelSettingRes.ok && labelSettingRes.data && typeof labelSettingRes.data === "object" ? labelSettingRes.data : {};
      const writerSummary = writerRes.ok && writerRes.data && typeof writerRes.data === "object" ? writerRes.data : {};
      const publishAuto = publishAutoRes.ok && publishAutoRes.data && typeof publishAutoRes.data === "object" ? publishAutoRes.data : {};
      const monitorItems = Array.isArray(monitorRes?.data?.items) ? monitorRes.data.items : [];
      const collectStatus = collectStatusRes.ok && collectStatusRes.data && typeof collectStatusRes.data === "object" ? collectStatusRes.data : {};
      const writerStatus = writerStatusRes.ok && writerStatusRes.data && typeof writerStatusRes.data === "object" ? writerStatusRes.data : {};
      const automation = automationRes.ok && automationRes.data && typeof automationRes.data === "object" ? automationRes.data : {};
      if (automationRes.ok) renderAutomationStatus(automation);
      const collectAuto = automation.collect || {};
      const labelingAuto = automation.labeling || {};
      const writerAuto = automation.writer || {};
      const publishAutoUnified = automation.publish || publishAuto;

      const metricSpecs = [
        { key: "categories", label: "카테고리", node: "keyword" },
        { key: "keywords", label: "키워드", node: "keyword" },
        { key: "raw_contents", label: "수집 콘텐츠", node: "collect.contents" },
        { key: "crawl_jobs", label: "수집 작업", node: "collect.jobs" },
        { key: "personas", label: "페르소나", node: "writer.persona" },
        { key: "templates", label: "템플릿", node: "writer.template" },
        { key: "ai_providers", label: "AI API", node: "writer.ai" },
        { key: "writing_channels", label: "작성 채널", node: "writer.channels" },
        { key: "articles", label: "작성 결과", node: "writer.editor" },
        { key: "publish_channels", label: "발행 채널", node: "publish.settings" },
        { key: "publish_jobs", label: "발행 작업", node: "publish.history" },
      ];

      const collectTotal = collectJobs.length;
      const collectFailed = collectJobs.filter((j) => String(j.status || "").toLowerCase().includes("fail")).length;
      const collectFailRate = collectTotal ? (collectFailed / collectTotal) * 100 : 0;

      const labelContentTotal = Number(labelStats.contents_total || 0);
      const labelImageTotal = Number(labelStats.images_total || 0);
      const labelTotal = labelContentTotal + labelImageTotal;
      const labelDone = Number(labelStats.contents_labeled || 0) + Number(labelStats.images_labeled || 0);
      const labelCompletion = labelTotal ? (labelDone / labelTotal) * 100 : 100;
      const labelPending = Number(labelSnapshot.contents_pending || 0) + Number(labelSnapshot.images_pending || 0);

      const writerChannels = Array.isArray(writerSummary.channels) ? writerSummary.channels : [];
      const writerTotal = writerChannels.length;
      const writerUnready = writerChannels.filter((c) => !c.policy_ready).length;
      const writerUnreadyRate = writerTotal ? (writerUnready / writerTotal) * 100 : 0;

      const publishEvents = monitorItems.filter((e) => String(e.stage || "") === "publish");
      const publishTotal = publishEvents.length;
      const publishFailed = publishEvents.filter((e) => String(e.status || "").toLowerCase().includes("fail")).length;
      const publishFailRate = publishTotal ? (publishFailed / publishTotal) * 100 : 0;

      const monitorErrorCount = monitorItems.filter((e) => {
        const s = String(e.status || "").toLowerCase();
        return s.includes("fail") || s.includes("error");
      }).length;

      dashboardPushHistory("collect_fail_rate", collectFailRate);
      dashboardPushHistory("label_completion", labelCompletion);
      dashboardPushHistory("writer_unready_rate", writerUnreadyRate);
      dashboardPushHistory("publish_fail_rate", publishFailRate);
      dashboardPushHistory("monitor_error_count", monitorErrorCount);
      dashboardWritePrefs();

      const collectDashboardErr = String(collectAuto.last_error || "").trim();
      const writerDashboardErr = String(writerAuto.last_error || "").trim();
      const publishLogs = Array.isArray(publishAutoUnified.logs) ? publishAutoUnified.logs : [];
      const publishDashboardErr = [...publishLogs].reverse().find((line) => /(실패|오류|error)/i.test(String(line || ""))) || "";

      const collectAutoState = collectDashboardErr
        ? "error"
        : (collectStatus.running ? "running" : (collectAuto.worker_started ? "waiting" : "stopped"));
      const writerAutoState = writerDashboardErr
        ? "error"
        : (writerStatus.running ? "running" : (writerAuto.worker_started ? "waiting" : "stopped"));
      const labelingAutoState = String(labelingAuto.last_error || "").trim()
        ? "error"
        : (labelingAuto.running ? "running" : (labelingAuto.auto_enabled ? "waiting" : "stopped"));
      const publishAutoState = publishDashboardErr
        ? "error"
        : (publishAutoUnified.enabled ? (publishAutoUnified.pause_until ? "waiting" : "running") : "stopped");

      const statusCards = [
        {
          title: "수집 실행 상태",
          value: collectAutoState === "running" ? "즉시실행중" : (collectAutoState === "waiting" ? "자동대기" : (collectAutoState === "error" ? "오류발생" : "자동중지")),
          state: collectAutoState,
          stateLabel: collectAutoState === "running" ? "실행중" : (collectAutoState === "waiting" ? "대기중" : (collectAutoState === "error" ? "오류" : "중지")),
          sub: collectStatus.stop_requested ? "중단 요청 처리중" : (collectDashboardErr ? `오류: ${collectDashboardErr}` : `다음 실행: ${fmt(collectAuto.next_run_at)}`),
          node: "collect.run",
          warn: !!collectStatus.stop_requested || !!collectDashboardErr,
        },
        {
          title: "작성 실행 상태",
          value: writerAutoState === "running" ? "즉시실행중" : (writerAutoState === "waiting" ? "자동대기" : (writerAutoState === "error" ? "오류발생" : "자동중지")),
          state: writerAutoState,
          stateLabel: writerAutoState === "running" ? "실행중" : (writerAutoState === "waiting" ? "대기중" : (writerAutoState === "error" ? "오류" : "중지")),
          sub: writerStatus.stop_requested
            ? "중단 요청 처리중"
            : (writerDashboardErr
              ? `오류: ${writerDashboardErr}`
              : `자동채널: ${writerAuto.auto_channel_count || 0}개 / 최근처리: ${writerAuto.last_tick_processed || 0}건`),
          node: "writer.run",
          warn: !!writerStatus.stop_requested || !!writerDashboardErr,
        },
        {
          title: "라벨 실행 상태",
          value: labelingAutoState === "running" ? "즉시실행중" : (labelingAutoState === "waiting" ? "자동대기" : (labelingAutoState === "error" ? "오류발생" : "자동중지")),
          state: labelingAutoState,
          stateLabel: labelingAutoState === "running" ? "실행중" : (labelingAutoState === "waiting" ? "대기중" : (labelingAutoState === "error" ? "오류" : "중지")),
          sub: labelingAuto.last_error
            ? `오류: ${labelingAuto.last_error}`
            : `주기 ${Number(labelingAuto.interval_minutes || 15)}분 / 최근 처리 ${Number(labelingAuto.last_content_processed || 0)}+${Number(labelingAuto.last_image_processed || 0)}건`,
          node: "label.run",
          warn: !labelingAuto.auto_enabled || !!labelingAuto.last_error,
        },
        {
          title: "자동 발행 상태",
          value: publishAutoState === "running" ? "자동실행중" : (publishAutoState === "waiting" ? "일시대기" : (publishAutoState === "error" ? "오류발생" : "자동중지")),
          state: publishAutoState,
          stateLabel: publishAutoState === "running" ? "실행중" : (publishAutoState === "waiting" ? "대기중" : (publishAutoState === "error" ? "오류" : "중지")),
          sub: publishDashboardErr
            ? `오류: ${publishDashboardErr}`
            : (publishAutoUnified.pause_until ? `일시중지: ${fmt(publishAutoUnified.pause_until)}` : `최근 실행: ${fmt(publishAutoUnified.last_tick_at)}`),
          node: "publish.run",
          warn: !publishAutoUnified.enabled || !!publishAutoUnified.pause_until || !!publishDashboardErr,
        },
      ];

      const metricCards = [
        {
          key: "collect_fail_rate",
          title: "수집 상태",
          value: `${collectFailRate.toFixed(1)}%`,
          sub: `실패 ${collectFailed}/${collectTotal}`,
          node: "collect.jobs",
          warn: collectFailRate >= Number(state.dashboardThresholds.collect_fail || 20),
        },
        {
          key: "label_completion",
          title: "라벨링 완료율",
          value: `${labelCompletion.toFixed(1)}%`,
          sub: `완료 ${labelDone}/${labelTotal}`,
          node: "label.results",
          warn: labelCompletion < 95,
        },
        {
          key: "writer_unready_rate",
          title: "작성 준비도",
          value: `${(100 - writerUnreadyRate).toFixed(1)}%`,
          sub: `미준비 ${writerUnready}/${writerTotal}`,
          node: "writer.run",
          warn: writerUnreadyRate >= Number(state.dashboardThresholds.writer_unready || 30),
        },
        {
          key: "publish_fail_rate",
          title: "발행 실패율",
          value: `${publishFailRate.toFixed(1)}%`,
          sub: `실패 ${publishFailed}/${publishTotal}`,
          node: "publish.history",
          warn: publishFailRate >= Number(state.dashboardThresholds.publish_fail || 20),
        },
        {
          key: "monitor_error_count",
          title: "모니터 오류",
          value: String(monitorErrorCount),
          sub: `최근 이벤트 ${monitorItems.length}건`,
          node: "monitor.logs",
          warn: monitorErrorCount >= Number(state.dashboardThresholds.monitor_errors || 5),
        },
      ];

      const countCards = metricSpecs.map((spec) => {
        const ok = summaryRes.ok && Object.prototype.hasOwnProperty.call(summary, spec.key);
        return {
          title: spec.label,
          value: ok ? String(Number(summary[spec.key] || 0)) : "ERR",
          sub: ok ? "정상" : "조회 실패",
          node: spec.node,
          warn: !ok,
        };
      });

      autoWrap.innerHTML = "";
      statusCards.forEach((card, idx) => {
        const div = document.createElement("button");
        div.type = "button";
        div.className = `card-metric dashboard-clickable dashboard-auto-card tone-${(idx % 3) + 1}`;
        div.classList.add(`state-${card.state || "stopped"}`);
        if (card.warn) div.classList.add("warn");
        if (card.value === "ERR") div.classList.add("fail");
        div.innerHTML = `
          <div class='metric-head'>
            <div class='metric-key'>${card.title}</div>
            <span class='dashboard-state-pill state-${card.state || "stopped"}'><span class='state-dot'></span>${card.stateLabel || "-"}</span>
          </div>
          <div class='metric-val'>${card.value}</div>
          <div class='metric-sub'>${card.sub}</div>
        `;
        div.addEventListener("click", () => navigateToNode(card.node));
        autoWrap.appendChild(div);
      });

      opsWrap.innerHTML = "";
      metricCards.forEach((card) => {
        const div = document.createElement("button");
        div.type = "button";
        div.className = "card-metric dashboard-clickable dashboard-ops-card";
        if (card.warn) div.classList.add("warn");
        const history = card.key ? (state.dashboardHistory[card.key] || []) : [];
        div.innerHTML = `
          <div class='metric-key'>${card.title}</div>
          <div class='metric-val'>${card.value}</div>
          <div class='metric-sub'>${card.sub}</div>
          ${card.key ? `<div class='metric-sparkline'>${dashboardSparkline(history)}</div>` : ""}
        `;
        div.addEventListener("click", () => navigateToNode(card.node));
        opsWrap.appendChild(div);
      });

      const labelingCards = [
        {
          title: "대기 큐",
          value: `${labelPending}건`,
          sub: `텍스트 ${Number(labelSnapshot.contents_pending || 0)} / 이미지 ${Number(labelSnapshot.images_pending || 0)}`,
          node: "label.run",
          warn: labelPending > Number(labelSetting.batch_size || 300),
        },
        {
          title: "완료율",
          value: `${Number(labelSnapshot.completion_rate || labelCompletion).toFixed(1)}%`,
          sub: `완료 ${Number(labelSnapshot.completed || labelDone)}/${Number(labelSnapshot.total || labelTotal)}`,
          node: "label.results",
          warn: Number(labelSnapshot.completion_rate || labelCompletion) < 95,
        },
        {
          title: "자동화 설정",
          value: String(labelSetting.method || "rule").toUpperCase(),
          sub: `배치 ${Number(labelSetting.batch_size || 300)} | 품질 ${Number(labelSetting.quality_threshold || 3)} | Free 잔여 ${Number(labelSnapshot.free_api_remaining_today || 0)} | Paid 잔여 ${Number(labelSnapshot.paid_api_remaining_today || 0)}`,
          node: "label.settings",
          warn: false,
        },
        {
          title: "최근 처리",
          value: fmt(labelSnapshot.last_content_labeled_at || labelSnapshot.last_image_labeled_at),
          sub: `평균 품질 텍스트 ${Number(labelSnapshot.avg_content_quality || 0).toFixed(1)} / 이미지 ${Number(labelSnapshot.avg_image_quality || 0).toFixed(1)} | route rule ${Number((labelSnapshot.content_method_breakdown || {}).rule || 0) + Number((labelSnapshot.image_method_breakdown || {}).rule || 0)} / free ${Number((labelSnapshot.content_method_breakdown || {}).free_api || 0) + Number((labelSnapshot.image_method_breakdown || {}).free_api || 0)} / paid ${Number((labelSnapshot.content_method_breakdown || {}).paid_api || 0) + Number((labelSnapshot.image_method_breakdown || {}).paid_api || 0)}`,
          node: "label.run",
          warn: !labelSnapshot.last_content_labeled_at && !labelSnapshot.last_image_labeled_at,
        },
      ];

      labelingWrap.innerHTML = "";
      labelingCards.forEach((card) => {
        const div = document.createElement("button");
        div.type = "button";
        div.className = "card-metric dashboard-clickable dashboard-label-card";
        if (card.warn) div.classList.add("warn");
        div.innerHTML = `
          <div class='metric-key'>${card.title}</div>
          <div class='metric-val'>${card.value || "-"}</div>
          <div class='metric-sub'>${card.sub || "-"}</div>
        `;
        div.addEventListener("click", () => navigateToNode(card.node));
        labelingWrap.appendChild(div);
      });
      if (labelingHint) {
        labelingHint.textContent = labelSnapshotRes.ok && labelSettingRes.ok
          ? `라벨링 방식 ${String(labelSetting.method || "rule")} | 다음 실행은 라벨링 실행 메뉴에서 즉시 트리거 가능합니다.`
          : "라벨링 자동화 지표 일부를 불러오지 못했습니다.";
      }

      resourceWrap.innerHTML = "";
      countCards.forEach((card) => {
        const div = document.createElement("button");
        div.type = "button";
        div.className = "card-metric dashboard-clickable dashboard-resource-card";
        if (card.warn) div.classList.add("warn");
        if (card.value === "ERR") div.classList.add("fail");
        div.innerHTML = `
          <div class='metric-key'>${card.title}</div>
          <div class='metric-val'>${card.value}</div>
          <div class='metric-sub'>${card.sub}</div>
        `;
        div.addEventListener("click", () => navigateToNode(card.node));
        resourceWrap.appendChild(div);
      });

      const failApis = [
        summaryRes.ok ? null : "dashboard/summary",
        collectJobsRes.ok ? null : "collect/jobs",
        labelStatsRes.ok ? null : "labeling/stats",
        labelSnapshotRes.ok ? null : "labeling/automation-snapshot",
        labelSettingRes.ok ? null : "v2/settings/label",
        writerRes.ok ? null : "writer/run-summary",
        publishAutoRes.ok ? null : "publish/auto/status",
        monitorRes.ok ? null : "v2/monitor/events",
        collectStatusRes.ok ? null : "collect/status",
        writerStatusRes.ok ? null : "writer/status",
        automationRes.ok ? null : "automation/status",
      ].filter(Boolean);
      if (hint) {
        hint.textContent = failApis.length
          ? `부분 실패: ${failApis.join(", ")} | 마지막 갱신 ${fmt(new Date().toISOString())}`
          : `정상 | 자동새로고침 ${state.dashboardAutoRefreshEnabled ? `ON(${state.dashboardAutoRefreshSec}s)` : "OFF"} | 마지막 갱신 ${fmt(new Date().toISOString())}`;
      }

      startDashboardPolling();
    }

    return {
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
    };
  }

  window.createDashboardModule = createDashboardModule;
})();
