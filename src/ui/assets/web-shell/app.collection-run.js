(() => {
  function createCollectionRunModule(ctx) {
    const {
      qs,
      state,
      request,
      showAlert,
      showConfirm,
      renderCollectFilters,
      renderCollectSummary,
      scopeLabel,
      persistCollectLogState,
    } = ctx || {};

    function renderCollectLogDashboard() {
      const tbody = qs("#collectLogTable tbody");
      if (!tbody) return;
      if (!state.collectRunLogs.length) {
        tbody.innerHTML = "<tr><td>실행 로그 없음</td></tr>";
        return;
      }
      tbody.innerHTML = "";
      state.collectRunLogs.forEach((line) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${line}</td>`;
        tbody.appendChild(tr);
      });
    }

    function appendCollectLogs(messages) {
      const ts = new Date().toLocaleString("ko-KR");
      (messages || []).forEach((m) => {
        state.collectRunLogs.unshift(`[${ts}] ${m}`);
      });
      if (state.collectRunLogs.length > 25) {
        state.collectRunLogs = state.collectRunLogs.slice(0, 25);
      }
      persistCollectLogState();
      renderCollectLogDashboard();
    }

    function syncCollectJobsToLogs(jobs) {
      const rows = Array.isArray(jobs) ? jobs : [];
      state.collectLatestJobs = rows;
      const isFirstSync = Object.keys(state.collectJobState || {}).length === 0 && state.collectRunLogs.length === 0;
      rows.forEach((job) => {
        const id = Number(job.id || 0);
        if (!id) return;
        const key = String(id);
        const status = String(job.status || "");
        const collected = Number(job.collected_count || 0);
        const sig = `${status}:${collected}`;
        if (isFirstSync) {
          state.collectJobState[key] = sig;
          return;
        }
        if (state.collectJobState[key] === sig) return;
        state.collectJobState[key] = sig;
        appendCollectLogs([`작업 #${id} | ${job.keyword || "-"} | ${job.channel_code || "-"} | ${status || "-"} | 수집 ${collected}건`]);
      });
      persistCollectLogState();
    }

    function updateCollectRunControls(isRunning = false, stopRequested = false) {
      const runBtn = qs("#collectRunBtn");
      const stopBtn = qs("#collectStopBtn");
      if (runBtn) {
        runBtn.disabled = !!isRunning;
        runBtn.textContent = isRunning ? "수집 실행중..." : "수집 실행";
      }
      if (stopBtn) {
        stopBtn.disabled = !isRunning || !!stopRequested;
        stopBtn.textContent = stopRequested ? "중단 요청됨" : "중단";
      }
    }

    function syncCollectRunStatus(status) {
      const running = !!status?.running;
      const stopRequested = !!status?.stop_requested;
      state.collectIsRunning = running;
      const sig = `${running ? 1 : 0}:${stopRequested ? 1 : 0}`;
      if (state.collectStatusSig !== sig) {
        if (running && stopRequested) appendCollectLogs(["중단 요청 접수됨: 현재 작업 종료 후 중단됩니다."]);
        if (!running && state.collectStatusSig.startsWith("1:")) appendCollectLogs(["수집 실행이 종료되었습니다."]);
        state.collectStatusSig = sig;
      }
      updateCollectRunControls(running, stopRequested);
    }

    async function stopCollect() {
      if (!state.collectIsRunning) return showAlert("현재 실행 중인 수집이 없습니다.", "알림", "warn");
      const ok = await showConfirm("현재 수집 실행을 중단하시겠습니까?\n(진행 중인 채널 작업은 완료 후 중단됩니다)", "중단 확인", "warn");
      if (!ok) return;
      await request("/api/collect/stop", { method: "POST", body: "{}" });
      appendCollectLogs(["중단 요청 전송"]);
      updateCollectRunControls(true, true);
    }

    function stopCollectionPolling() {
      if (state.collectPollTimer) {
        clearInterval(state.collectPollTimer);
        state.collectPollTimer = null;
      }
    }

    function startCollectionPolling() {
      stopCollectionPolling();
      state.collectPollTimer = setInterval(() => {
        refreshCollectionSection().catch(() => {});
      }, 2500);
    }

    async function refreshCollectionSection() {
      const [channels, kws, collectSettings, jobs, collectStatus] = await Promise.all([
        request("/api/source-channels"),
        request("/api/collect/keywords"),
        request("/api/v2/settings/collect"),
        request("/api/collect/jobs"),
        request("/api/collect/status").catch(() => ({ running: false, stop_requested: false })),
      ]);
      state.collectSettings = collectSettings || null;
      renderCollectFilters(kws);
      renderCollectSummary(collectSettings, channels, kws);
      const maxInput = qs("#collectMaxResults");
      if (maxInput) {
        maxInput.value = String(collectSettings?.max_results || 3);
      }
      syncCollectJobsToLogs(jobs);
      syncCollectRunStatus(collectStatus);
      renderCollectLogDashboard();
    }

    async function runCollect() {
      if (state.collectIsRunning) return showAlert("이미 수집 실행 중입니다.", "알림", "warn");
      const scope = String(state.collectSettings?.keyword_scope || "selected");
      const maxResults = Number(state.collectSettings?.max_results || 3);

      const ok = await showConfirm(`[실행 확인]\n모드: ${scopeLabel(scope)}\n최대 수집: ${maxResults}개\n\n현재 설정으로 수집을 실행하시겠습니까?`, "실행 확인", "warn");
      if (!ok) return;

      appendCollectLogs([`수집 실행 요청: mode=${scope}, max=${maxResults}`]);
      updateCollectRunControls(true, false);
      const result = await request("/api/collect/run", {
        method: "POST",
        body: JSON.stringify({ keyword_id: null, max_results: maxResults }),
      });
      appendCollectLogs(result.messages || ["수집 실행 완료"]);
      if (result?.stopped) showAlert("중단 요청으로 수집 실행이 종료되었습니다.", "중단 완료", "warn");
      await refreshCollectionSection();
    }

    return {
      renderCollectLogDashboard,
      appendCollectLogs,
      stopCollect,
      stopCollectionPolling,
      startCollectionPolling,
      refreshCollectionSection,
      runCollect,
    };
  }

  window.createCollectionRunModule = createCollectionRunModule;
})();
