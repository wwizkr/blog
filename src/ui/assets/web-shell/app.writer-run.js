(() => {
  function createWriterRunModule(ctx) {
    const {
      qs,
      state,
      request,
      fmt,
      selectValueIfExists,
      showAlert,
      appendWriterLogs,
      refreshWriterRunChannelMetricHint,
    } = ctx || {};

    function renderWriterLogDashboard() {
      const tbody = qs("#writerLogTable tbody");
      if (!tbody) return;
      if (!state.writerRunLogs.length) {
        tbody.innerHTML = "<tr><td>실행 로그 없음</td></tr>";
        return;
      }
      tbody.innerHTML = "";
      state.writerRunLogs.forEach((line) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${line}</td>`;
        tbody.appendChild(tr);
      });
    }

    function updateWriterRunControls(isRunning = false, stopRequested = false) {
      const runBtn = qs("#writerRunBtn");
      const stopBtn = qs("#writerStopBtn");
      const resumeBtn = qs("#writerResumeBtn");
      if (runBtn) {
        runBtn.disabled = !!isRunning;
        runBtn.textContent = isRunning ? "글 작성 실행중..." : "글 작성 실행";
      }
      if (stopBtn) {
        stopBtn.disabled = !isRunning || !!stopRequested;
        stopBtn.textContent = stopRequested ? "중단 요청됨" : "중단";
      }
      if (resumeBtn) {
        resumeBtn.disabled = !!isRunning;
      }
      const hint = qs("#writerRunStatusHint");
      if (hint) {
        if (isRunning) {
          hint.textContent = stopRequested ? "취소 요청됨: 현재 채널/회차 처리 후 종료" : "실행 중";
        } else {
          const last = state.writerRunLogs[0] || "";
          if (String(last).includes("중단")) hint.textContent = "중단됨(재개 가능)";
          else if (String(last).includes("완료")) hint.textContent = "완료";
          else hint.textContent = "대기 중";
        }
      }
    }

    async function refreshWriterRunSummary() {
      const [summary, status] = await Promise.all([
        request("/api/writer/run-summary").catch(() => ({ channels: [] })),
        request("/api/writer/status").catch(() => ({ running: false, stop_requested: false })),
      ]);

      const channels = summary.channels || [];
      const readyCount = channels.filter((c) => c.policy_ready).length;
      const batchTotal = channels.reduce((acc, c) => acc + Number(c.auto_batch_count || 0), 0);
      const autoEnabled = channels.filter((c) => !!c.auto_enabled).length;

      qs("#writerSummaryChannelCount").textContent = String(channels.length);
      qs("#writerSummaryPolicyReady").textContent = `${readyCount}/${channels.length}`;
      qs("#writerSummaryBatchTotal").textContent = String(batchTotal);
      qs("#writerSummaryAutoEnabled").textContent = `${autoEnabled}/${channels.length}`;

      const tbody = qs("#writerSummaryTable tbody");
      if (tbody) {
        tbody.innerHTML = channels.length ? "" : "<tr><td colspan='6'>활성 작성 채널 없음</td></tr>";
        channels.forEach((row) => {
          const statusText = row.policy_ready ? "준비됨" : "정책 미완성";
          const tr = document.createElement("tr");
          tr.innerHTML = `<td>${row.channel_name}</td><td>${row.persona_count}개</td><td>${row.template_count}개</td><td>${row.ai_provider_name || "-"}</td><td>${row.auto_batch_count}</td><td>${statusText}</td>`;
          tbody.appendChild(tr);
        });
      }

      state.writerStatus = { running: !!status.running, stop_requested: !!status.stop_requested };
      updateWriterRunControls(state.writerStatus.running, state.writerStatus.stop_requested);
      refreshWriterRunChannelMetricHint();
      await refreshWriterResultBoard();
    }

    async function refreshWriterResultBoard() {
      const payload = await request("/api/writer/result-board").catch(() => ({ items: [], publish_channels: [] }));
      const rows = Array.isArray(payload.items) ? payload.items : [];
      const channels = Array.isArray(payload.publish_channels) ? payload.publish_channels : [];
      state.writerBoardRows = rows;
      const validIds = new Set(rows.map((r) => Number(r.id || 0)));
      setWriterBoardSelectedIds(getSelectedWriterBoardIds().filter((id) => validIds.has(id)));

      const channelSel = qs("#writerBoardPublishChannel");
      if (channelSel) {
        const prev = String(channelSel.value || "");
        channelSel.innerHTML = "";
        channels.forEach((c) => {
          const o = document.createElement("option");
          o.value = String(c.code);
          o.textContent = c.auto_allowed ? `${c.display_name} (${c.code})` : `${c.display_name} (${c.code}) - 자동발행 미허용`;
          o.disabled = !c.auto_allowed;
          channelSel.appendChild(o);
        });
        if (!selectValueIfExists(channelSel, prev)) {
          const firstAuto = channels.find((c) => !!c.auto_allowed);
          if (firstAuto) channelSel.value = String(firstAuto.code);
        }
      }

      renderWriterBoardTable();
    }

    function getSelectedWriterBoardIds() {
      return [...new Set((state.writerBoardSelectedIds || []).map((v) => Number(v)).filter((v) => Number.isFinite(v) && v > 0))];
    }

    function setWriterBoardSelectedIds(ids) {
      state.writerBoardSelectedIds = [...new Set((ids || []).map((v) => Number(v)).filter((v) => Number.isFinite(v) && v > 0))];
    }

    function updateWriterBoardPickAllState(pageRows) {
      const all = qs("#writerBoardPickAll");
      if (!all) return;
      const rows = Array.isArray(pageRows) ? pageRows : [];
      const selected = new Set(getSelectedWriterBoardIds());
      const selectedOnPage = rows.filter((r) => selected.has(Number(r.id))).length;
      all.checked = rows.length > 0 && selectedOnPage === rows.length;
    }

    function registerWriterBoardHistory(articleId, message) {
      const id = Number(articleId || 0);
      if (!id) return;
      const key = String(id);
      const next = { ...(state.writerBoardStatusHistory || {}) };
      const arr = Array.isArray(next[key]) ? next[key] : [];
      arr.unshift(`[${new Date().toLocaleString("ko-KR")}] ${String(message || "")}`);
      next[key] = arr.slice(0, 30);
      state.writerBoardStatusHistory = next;
    }

    async function openWriterBoardHistory(articleRow) {
      if (!articleRow) return;
      const articleId = Number(articleRow.id || 0);
      const jobs = await request("/api/publisher/jobs").catch(() => []);
      const filtered = (Array.isArray(jobs) ? jobs : []).filter((j) => Number(j.article_id || 0) === articleId);
      const local = (state.writerBoardStatusHistory || {})[String(articleId)] || [];
      const lines = [
        `글 #${articleId} 히스토리`,
        `- 생성: ${fmt(articleRow.created_at)}`,
        `- 현재 작성상태: ${writerArticleStatusLabel(articleRow.article_status)}`,
        `- 현재 발행상태: ${articleRow.publish_status || "-"}`,
      ];
      if (articleRow.seo_review && typeof articleRow.seo_review === "object") {
        lines.push(`- SEO 검수: ${Number(articleRow.seo_review.score || 0)}점 / ${articleRow.seo_review.status || "-"}`);
        const flags = Array.isArray(articleRow.seo_review.flags) ? articleRow.seo_review.flags : [];
        flags.slice(0, 5).forEach((flag) => lines.push(`  · ${flag}`));
        const recommendations = Array.isArray(articleRow.seo_review.recommendations) ? articleRow.seo_review.recommendations : [];
        if (recommendations.length) {
          lines.push("  [보완 가이드]");
          recommendations.slice(0, 3).forEach((item) => lines.push(`  · ${item}`));
        }
      }
      if (articleRow.last_published_at) lines.push(`- 마지막 발행: ${fmt(articleRow.last_published_at)}`);
      if (filtered.length) {
        lines.push("");
        lines.push("[발행 작업 이력]");
        filtered.slice(0, 10).forEach((j) => {
          lines.push(`- ${fmt(j.created_at)} | ${j.target_channel || "-"} | ${j.status || "-"} | ${j.message || ""}`);
        });
      }
      if (local.length) {
        lines.push("");
        lines.push("[로컬 상태 변경 이력]");
        local.slice(0, 10).forEach((line) => lines.push(`- ${line}`));
      }
      showAlert(lines.join("\n"), "상태 히스토리", "info");
    }

    async function preflightPublishWriterBoardArticle(articleId, targetChannel) {
      const id = Number(articleId || 0);
      if (!id) throw new Error("발행할 글이 올바르지 않습니다.");
      if (!String(targetChannel || "").trim()) throw new Error("발행 채널을 선택하세요.");
      const [article, personas] = await Promise.all([
        request(`/api/writer/articles/${id}`),
        request("/api/personas").catch(() => []),
      ]);
      const title = String(article?.title || "").trim();
      const content = String(article?.content || "").trim();
      if (!title) throw new Error("사전 검증 실패: 제목이 비어 있습니다.");
      if (!content) throw new Error("사전 검증 실패: 본문이 비어 있습니다.");
      const bannedWords = (Array.isArray(personas) ? personas : [])
        .flatMap((p) => String(p.banned_words || "").split(","))
        .map((w) => w.trim())
        .filter(Boolean);
      const hit = bannedWords.find((w) => content.includes(w) || title.includes(w));
      if (hit) throw new Error(`사전 검증 실패: 금칙어 포함 (${hit})`);
      return { ok: true };
    }

    function writerArticleStatusLabel(status) {
      const s = String(status || "").toLowerCase();
      if (s === "draft") return "초안";
      if (s === "ready") return "발행대기";
      if (s === "published") return "발행완료";
      if (s === "failed") return "실패";
      return status || "-";
    }

    function writerSeoReviewBadge(review) {
      const item = review && typeof review === "object" ? review : {};
      const score = Number(item.score || 0);
      const status = String(item.status || "기준없음");
      if (status === "양호") return `<span class="badge-status ok">${score}점 · ${status}</span>`;
      if (status === "보통") return `<span class="badge-status warn">${score}점 · ${status}</span>`;
      return `<span class="badge-status neutral">${score}점 · ${status}</span>`;
    }

    function closeWriterArticleEditor() {
      const modal = qs("#writerArticleModal");
      if (!modal) return;
      modal.classList.add("hidden");
      modal.setAttribute("aria-hidden", "true");
      state.writerEditingArticleId = null;
    }

    function closeWriterArticleViewer() {
      const modal = qs("#writerArticleViewModal");
      if (!modal) return;
      modal.classList.add("hidden");
      modal.setAttribute("aria-hidden", "true");
      state.writerViewingArticleId = null;
    }

    function setWriterArticlePreviewContent(content) {
      const target = qs("#writerArticleViewContent");
      if (!target) return;
      const text = String(content || "");
      if (/<\/?[a-z][^>]*>/i.test(text)) {
        target.innerHTML = text;
        return;
      }
      target.textContent = text;
    }

    function renderWriterArticleHero(imageAssets) {
      const target = qs("#writerArticleHero");
      if (!target) return;
      const asset = Array.isArray(imageAssets) ? imageAssets.find((item) => !!item?.local_url) : null;
      if (!asset) {
        target.classList.add("hidden");
        target.innerHTML = "";
        return;
      }
      const tags = Array.isArray(asset.subject_tags) ? asset.subject_tags.filter(Boolean).slice(0, 5) : [];
      const meta = [
        asset.image_type ? `type ${asset.image_type}` : "",
        Number(asset.keyword_relevance_score || 0) ? `적합 ${Number(asset.keyword_relevance_score || 0)}` : "",
        Number(asset.thumbnail_score || 0) ? `썸네일 ${Number(asset.thumbnail_score || 0)}` : "",
        Number(asset.commercial_intent || 0) ? `광고 ${Number(asset.commercial_intent || 0)}` : "",
      ].filter(Boolean).join(" | ");
      target.innerHTML = `
        <div class="writer-article-hero-label">대표 이미지</div>
        <img class="writer-article-hero-image" src="${escapePreviewHtml(asset.local_url)}" alt="대표 이미지" loading="lazy" />
        <div class="writer-article-hero-meta">${escapePreviewHtml(meta || "선택된 대표 이미지")}</div>
        ${tags.length ? `<div class="writer-article-hero-tags">${escapePreviewHtml(tags.join(", "))}</div>` : ""}
      `;
      target.classList.remove("hidden");
    }

    function escapePreviewHtml(value) {
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function renderWriterArticlePreview(content, imageAssets) {
      const assetMap = new Map();
      (Array.isArray(imageAssets) ? imageAssets : []).forEach((item) => {
        const id = Number(item?.id || 0);
        if (id > 0) assetMap.set(id, item);
      });
      const lines = String(content || "").split(/\r?\n/);
      const htmlLines = lines.map((line) => {
        const trimmed = String(line || "").trim();
        const match = trimmed.match(/^\[\[IMAGE:(\d+)\]\](?:\s*-\s*(.*))?$/);
        if (!match) return escapePreviewHtml(line);
        const imageId = Number(match[1] || 0);
        const caption = String(match[2] || "").trim();
        const asset = assetMap.get(imageId);
        if (!asset?.local_url) {
          return `<div class="writer-image-missing">이미지 ${imageId} 미리보기 없음</div>`;
        }
        const tags = Array.isArray(asset.subject_tags) ? asset.subject_tags.filter(Boolean).slice(0, 4) : [];
        const metaBits = [
          asset.image_type ? `type ${asset.image_type}` : "",
          Number(asset.keyword_relevance_score || 0) ? `적합 ${Number(asset.keyword_relevance_score || 0)}` : "",
          Number(asset.commercial_intent || 0) ? `광고 ${Number(asset.commercial_intent || 0)}` : "",
          tags.length ? `tags ${tags.join(", ")}` : "",
        ].filter(Boolean);
        const captionParts = [
          caption ? `<div class="writer-inline-image-title">${escapePreviewHtml(caption)}</div>` : "",
          metaBits.length ? `<div class="writer-inline-image-meta">${escapePreviewHtml(metaBits.join(" | "))}</div>` : "",
        ].filter(Boolean).join("");
        const captionHtml = captionParts ? `<figcaption>${captionParts}</figcaption>` : "";
        return `<figure class="writer-inline-image"><img src="${escapePreviewHtml(asset.local_url)}" alt="${escapePreviewHtml(caption || `image-${imageId}`)}" loading="lazy" />${captionHtml}</figure>`;
      });
      return htmlLines.join("<br>");
    }

    async function openWriterArticleEditor(articleId) {
      const id = Number(articleId || 0);
      if (!id) throw new Error("수정할 글이 올바르지 않습니다.");
      const article = await request(`/api/writer/articles/${id}`);
      state.writerEditingArticleId = id;
      qs("#writerArticleEditTitle").value = String(article?.title || "");
      qs("#writerArticleEditContent").value = String(article?.content || "");
      const review = article?.seo_review || {};
      const flags = Array.isArray(review.flags) ? review.flags : [];
      const recommendations = Array.isArray(review.recommendations) ? review.recommendations : [];
      const hint = qs("#writerArticleReviewHint");
      if (hint) {
        const firstHint = recommendations[0] || flags[0] || "-";
        hint.textContent = `SEO 검수 ${Number(review.score || 0)}점 / ${review.status || "-"} | ${firstHint}`;
      }
      const modal = qs("#writerArticleModal");
      if (modal) {
        modal.classList.remove("hidden");
        modal.setAttribute("aria-hidden", "false");
      }
    }

    async function openWriterArticleViewer(articleId) {
      const id = Number(articleId || 0);
      if (!id) throw new Error("볼 글이 올바르지 않습니다.");
      const article = await request(`/api/writer/articles/${id}`);
      state.writerViewingArticleId = id;
      const titleInput = qs("#writerArticleViewTitleInput");
      if (titleInput) titleInput.value = String(article?.title || "");
      const review = article?.seo_review || {};
      const flags = Array.isArray(review.flags) ? review.flags : [];
      const meta = qs("#writerArticleViewMeta");
      if (meta) {
        meta.textContent = `SEO 검수 ${Number(review.score || 0)}점 / ${review.status || "-"} | ${flags[0] || "보기 전용"}`;
      }
      renderWriterArticleHero(article?.image_assets || []);
      setWriterArticlePreviewContent(renderWriterArticlePreview(article?.content || "", article?.image_assets || []));
      const modal = qs("#writerArticleViewModal");
      if (modal) {
        modal.classList.remove("hidden");
        modal.setAttribute("aria-hidden", "false");
      }
    }

    async function saveWriterArticleEditor() {
      const id = Number(state.writerEditingArticleId || 0);
      if (!id) throw new Error("저장할 글이 선택되지 않았습니다.");
      await request(`/api/writer/articles/${id}/save`, {
        method: "POST",
        body: JSON.stringify({
          title: qs("#writerArticleEditTitle")?.value || "",
          content: qs("#writerArticleEditContent")?.value || "",
        }),
      });
      closeWriterArticleEditor();
      await refreshWriterResultBoard();
      showAlert("작성 결과가 저장되었습니다.", "성공", "success");
    }

    async function regenerateWriterArticle(articleId) {
      const id = Number(articleId || 0);
      if (!id) throw new Error("재생성할 글이 올바르지 않습니다.");
      const result = await request(`/api/writer/articles/${id}/regenerate`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      registerWriterBoardHistory(id, "재생성 실행");
      await refreshWriterResultBoard();
      const editingId = Number(state.writerEditingArticleId || 0);
      if (editingId === id) {
        await openWriterArticleEditor(id);
      }
      showAlert(`글을 다시 생성했습니다. ${result?.seo_profile_used ? "SEO 패턴 반영" : "일반 작성"}`, "재생성 완료", "success");
    }

    function getFilteredWriterBoardRows() {
      const all = state.writerBoardRows || [];
      const status = String(state.writerBoardStatusFilter || "all");
      const text = String(state.writerBoardSearch || "").trim().toLowerCase();

      return all.filter((row) => {
        const articleStatus = String(row.article_status || "").toLowerCase();
        const publishStatus = String(row.publish_status || "");
        if (status === "draft" && articleStatus !== "draft") return false;
        if (status === "ready" && articleStatus !== "ready") return false;
        if (status === "publish_done" && publishStatus !== "발행완료") return false;
        if (status === "publish_failed" && publishStatus !== "발행실패") return false;
        if (status === "unpublished" && publishStatus !== "미발행") return false;

        if (!text) return true;
        const haystack = `${row.id || ""} ${row.title || ""} ${writerArticleStatusLabel(row.article_status)} ${row.publish_status || ""} ${row.publish_channel || ""}`.toLowerCase();
        return haystack.includes(text);
      });
    }

    function renderWriterBoardPager(totalCount, totalPages) {
      const wrap = qs("#writerBoardPager");
      if (!wrap) return;
      wrap.innerHTML = "";
      const info = document.createElement("span");
      info.className = "pager-info";
      if (!totalCount) {
        info.textContent = "0개";
        wrap.appendChild(info);
        return;
      }
      const current = Math.min(Math.max(1, state.writerBoardPage), totalPages);
      info.textContent = `총 ${totalCount}개 / ${current} / ${totalPages} 페이지`;

      const prevBtn = document.createElement("button");
      prevBtn.type = "button";
      prevBtn.className = "btn ghost";
      prevBtn.textContent = "이전";
      prevBtn.disabled = current <= 1;
      prevBtn.addEventListener("click", () => {
        if (state.writerBoardPage <= 1) return;
        state.writerBoardPage -= 1;
        renderWriterBoardTable();
      });

      const nextBtn = document.createElement("button");
      nextBtn.type = "button";
      nextBtn.className = "btn ghost";
      nextBtn.textContent = "다음";
      nextBtn.disabled = current >= totalPages;
      nextBtn.addEventListener("click", () => {
        if (state.writerBoardPage >= totalPages) return;
        state.writerBoardPage += 1;
        renderWriterBoardTable();
      });

      wrap.appendChild(prevBtn);
      wrap.appendChild(nextBtn);
      wrap.appendChild(info);
    }

    function renderWriterBoardTable() {
      const rows = getFilteredWriterBoardRows();

      const tbody = qs("#writerBoardTable tbody");
      if (!tbody) return;
      const totalCount = rows.length;
      const totalPages = Math.max(1, Math.ceil(totalCount / state.writerBoardPageSize));
      state.writerBoardPage = Math.min(Math.max(1, state.writerBoardPage), totalPages);
      const start = (state.writerBoardPage - 1) * state.writerBoardPageSize;
      const pageRows = rows.slice(start, start + state.writerBoardPageSize);

      tbody.innerHTML = pageRows.length ? "" : "<tr><td colspan='9'>작성 결과가 없습니다.</td></tr>";
      const selected = new Set(getSelectedWriterBoardIds());
      pageRows.forEach((r) => {
        const tr = document.createElement("tr");
        const review = r.seo_review || {};
        const reviewHint = Array.isArray(review.recommendations) && review.recommendations.length
          ? review.recommendations[0]
          : ((Array.isArray(review.flags) && review.flags.length) ? review.flags[0] : "");
        const reviewFlags = reviewHint
          ? `<div class="label-badge-row"><span class="badge-channel">${reviewHint}</span></div>`
          : "";
        tr.innerHTML = `<td><input type="checkbox" data-action="pick-row" ${selected.has(Number(r.id)) ? "checked" : ""}/></td><td>${r.id}</td><td>${r.title || ""}</td><td>${writerSeoReviewBadge(review)}${reviewFlags}</td><td>${writerArticleStatusLabel(r.article_status)}</td><td>${r.publish_status || "-"}</td><td>${r.publish_channel || "-"}</td><td>${fmt(r.created_at)}</td><td><button class="btn ghost" data-action="view-article">보기</button> <button class="btn ghost" data-action="edit-article">수정</button> <button class="btn ghost" data-action="regenerate-article">재생성</button> <button class="btn" data-action="publish-now">즉시 발행</button> <button class="btn ghost" data-action="show-history">히스토리</button></td>`;
        tr.querySelector("[data-action='pick-row']")?.addEventListener("change", (e) => {
          const ids = new Set(getSelectedWriterBoardIds());
          const id = Number(r.id || 0);
          if (e.target.checked) ids.add(id);
          else ids.delete(id);
          setWriterBoardSelectedIds([...ids]);
          updateWriterBoardPickAllState(pageRows);
        });
        tr.querySelector("[data-action='view-article']")?.addEventListener("click", (e) => {
          e.stopPropagation();
          openWriterArticleViewer(Number(r.id || 0)).catch((err) => showAlert(String(err), "오류", "error"));
        });
        tr.querySelector("[data-action='edit-article']")?.addEventListener("click", (e) => {
          e.stopPropagation();
          openWriterArticleEditor(Number(r.id || 0)).catch((err) => showAlert(String(err), "오류", "error"));
        });
        tr.querySelector("[data-action='regenerate-article']")?.addEventListener("click", async (e) => {
          e.stopPropagation();
          try {
            await regenerateWriterArticle(Number(r.id || 0));
          } catch (err) {
            showAlert(String(err), "오류", "error");
          }
        });
        tr.querySelector("[data-action='publish-now']")?.addEventListener("click", async (e) => {
          e.stopPropagation();
          try {
            await preflightPublishWriterBoardArticle(Number(r.id || 0), String(qs("#writerBoardPublishChannel")?.value || ""));
            await publishWriterBoardArticle(Number(r.id || 0));
            registerWriterBoardHistory(Number(r.id || 0), "즉시 발행 실행");
            showAlert("즉시 발행이 완료되었습니다.", "성공", "success");
          } catch (err) {
            showAlert(String(err), "오류", "error");
          }
        });
        tr.querySelector("[data-action='show-history']")?.addEventListener("click", (e) => {
          e.stopPropagation();
          openWriterBoardHistory(r).catch((err) => showAlert(String(err), "오류", "error"));
        });
        tbody.appendChild(tr);
      });
      updateWriterBoardPickAllState(pageRows);
      renderWriterBoardPager(totalCount, totalPages);
    }

    async function publishWriterBoardArticle(articleId) {
      const id = Number(articleId || 0);
      const targetChannel = String(qs("#writerBoardPublishChannel")?.value || "").trim();
      if (!id) throw new Error("발행할 글이 올바르지 않습니다.");
      if (!targetChannel) throw new Error("자동 허용 발행 채널을 먼저 선택하세요.");
      await request("/api/writer/result-board/publish", {
        method: "POST",
        body: JSON.stringify({ article_id: id, target_channel: targetChannel }),
      });
      registerWriterBoardHistory(id, `즉시 발행 요청 채널=${targetChannel}`);
      await refreshWriterResultBoard();
    }

    async function bulkPublishWriterBoardArticles() {
      const ids = getSelectedWriterBoardIds();
      const targetChannel = String(qs("#writerBoardPublishChannel")?.value || "").trim();
      if (!ids.length) throw new Error("선택된 글이 없습니다.");
      if (!targetChannel) throw new Error("자동 허용 발행 채널을 먼저 선택하세요.");
      let success = 0;
      let failed = 0;
      for (const id of ids) {
        try {
          await preflightPublishWriterBoardArticle(id, targetChannel);
          await request("/api/writer/result-board/publish", {
            method: "POST",
            body: JSON.stringify({ article_id: id, target_channel: targetChannel }),
          });
          registerWriterBoardHistory(id, `일괄 즉시 발행 채널=${targetChannel}`);
          success += 1;
        } catch (_e) {
          failed += 1;
        }
      }
      await refreshWriterResultBoard();
      showAlert(`일괄 발행 완료: 성공 ${success}건 / 실패 ${failed}건`, "결과", failed ? "warn" : "success");
    }

    async function bulkUpdateWriterBoardStatus() {
      const ids = getSelectedWriterBoardIds();
      const status = String(qs("#writerBoardBulkStatus")?.value || "").trim();
      if (!ids.length) throw new Error("선택된 글이 없습니다.");
      if (!status) throw new Error("변경할 상태를 선택하세요.");
      const result = await request("/api/writer/articles/batch-status", {
        method: "POST",
        body: JSON.stringify({ article_ids: ids, status }),
      });
      const updatedCount = Number(result?.updated || 0);
      ids.slice(0, updatedCount).forEach((id) => registerWriterBoardHistory(id, `상태 변경 -> ${status}`));
      await refreshWriterResultBoard();
      const blocked = Array.isArray(result?.blocked) ? result.blocked : [];
      if (blocked.length) {
        const first = blocked[0];
        showAlert(`상태 변경 완료: 성공 ${updatedCount}건 / 차단 ${blocked.length}건\n첫 차단 사유: ${first.reason || "-"}`, "결과", updatedCount ? "warn" : "error");
        return;
      }
      showAlert(`상태가 ${updatedCount}건 변경되었습니다.`, "성공", "success");
    }

    async function runWriter() {
      updateWriterRunControls(true, false);
      appendWriterLogs(["글 작성 실행 요청"]);
      try {
        const result = await request("/api/writer/run", { method: "POST", body: "{}" });
        appendWriterLogs(result.messages || ["실행 완료"]);
        if (result.stopped) {
          appendWriterLogs([`중단됨: 생성 ${result.created_count || 0}건 / 처리채널 ${result.processed_channels || 0}건`]);
        } else {
          appendWriterLogs([`완료: 생성 ${result.created_count || 0}건 / 처리채널 ${result.processed_channels || 0}건`]);
        }
      } catch (e) {
        appendWriterLogs([`오류: ${String(e)}`]);
        throw e;
      } finally {
        await refreshWriterRunSummary();
      }
    }

    async function stopWriter() {
      const r = await request("/api/writer/stop", { method: "POST", body: "{}" });
      if (r?.requested) {
        appendWriterLogs(["중단 요청 접수"]);
        updateWriterRunControls(true, true);
      } else {
        appendWriterLogs(["중단할 실행 작업이 없습니다."]);
      }
    }

    function startWriterPolling() {
      stopWriterPolling();
      state.writerPollTimer = setInterval(async () => {
        try {
          const status = await request("/api/writer/status");
          state.writerStatus = { running: !!status.running, stop_requested: !!status.stop_requested };
          updateWriterRunControls(state.writerStatus.running, state.writerStatus.stop_requested);
        } catch (_e) {
          // ignore polling errors
        }
      }, 1500);
    }

    function stopWriterPolling() {
      if (state.writerPollTimer) {
        clearInterval(state.writerPollTimer);
        state.writerPollTimer = null;
      }
    }

    return {
      renderWriterLogDashboard,
      updateWriterRunControls,
      refreshWriterRunSummary,
      refreshWriterResultBoard,
      renderWriterBoardPager,
      renderWriterBoardTable,
      publishWriterBoardArticle,
      bulkPublishWriterBoardArticles,
      bulkUpdateWriterBoardStatus,
      openWriterArticleEditor,
      openWriterArticleViewer,
      closeWriterArticleEditor,
      closeWriterArticleViewer,
      saveWriterArticleEditor,
      regenerateWriterArticle,
      runWriter,
      stopWriter,
      startWriterPolling,
      stopWriterPolling,
    };
  }

  window.createWriterRunModule = createWriterRunModule;
})();
