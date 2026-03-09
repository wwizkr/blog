(() => {
  function createCollectedDataModule(ctx) {
    const {
      qs,
      state,
      request,
      fmt,
      showAlert,
      escapeHtml,
    } = ctx || {};

    function getMubloEditorApi() {
      if (typeof globalThis !== "undefined" && typeof globalThis.MubloEditor !== "undefined") {
        return globalThis.MubloEditor;
      }
      try {
        return typeof MubloEditor !== "undefined" ? MubloEditor : null;
      } catch (_e) {
        return null;
      }
    }

    function textToHtml(value) {
      const text = String(value || "").replace(/\r\n/g, "\n").trim();
      if (!text) return "";

      if (/<\/?[a-z][^>]*>/i.test(text)) return text;

      return text
        .split("\n\n")
        .map((chunk) => `<p>${escapeHtml(chunk).replace(/\n/g, "<br>")}</p>`)
        .join("");
    }

    function ensureCollectedContentEditor() {
      if (state.contentViewerEditor) return state.contentViewerEditor;
      const mublo = getMubloEditorApi();
      if (!mublo) return state.contentViewerEditor;
      const target = qs("#contentBodyHtml");
      if (!target) return null;
      state.contentViewerEditor = mublo.create("#contentBodyHtml", {
        toolbar: "full",
        height: "420px",
        showWordCount: false,
        readonly: true,
        placeholder: "수집 본문",
      });
      return state.contentViewerEditor;
    }

    function setCollectedContentHtml(html) {
      const editor = ensureCollectedContentEditor();
      if (editor) {
        editor.setHTML(html || "");
        return;
      }
      const fallback = qs("#contentBodyHtml");
      if (fallback) fallback.value = html || "";
    }

    function ensureWriterEditor() {
      if (state.writerEditor) return state.writerEditor;
      const mublo = getMubloEditorApi();
      if (!mublo) return state.writerEditor;
      const target = qs("#writerContent");
      if (!target) return null;
      state.writerEditor = mublo.create("#writerContent", {
        toolbar: "full",
        height: "420px",
        showWordCount: true,
        placeholder: "본문",
      });
      return state.writerEditor;
    }

    function setWriterContentHtml(html) {
      const editor = ensureWriterEditor();
      if (editor) {
        editor.setHTML(html || "");
        return;
      }
      const fallback = qs("#writerContent");
      if (fallback) fallback.value = html || "";
    }

    function getWriterContentHtml() {
      const editor = ensureWriterEditor();
      if (editor) return editor.getHTML();
      return qs("#writerContent")?.value || "";
    }

    function clearCollectedContentDetail() {
      const source = qs("#contentSourceUrl");
      if (source) source.value = "";
      setCollectedContentHtml("");
      const tone = qs("#contentTone");
      const sentiment = qs("#contentSentiment");
      const topics = qs("#contentTopics");
      const quality = qs("#contentQuality");
      const structureType = qs("#contentStructureType");
      const titleType = qs("#contentTitleType");
      const commercialIntent = qs("#contentCommercialIntent");
      const writingFitScore = qs("#contentWritingFitScore");
      const ctaPresent = qs("#contentCtaPresent");
      const faqStructure = qs("#contentFaqStructure");
      if (tone) tone.value = "";
      if (sentiment) sentiment.value = "";
      if (topics) topics.value = "";
      if (quality) quality.value = 3;
      if (structureType) structureType.value = "";
      if (titleType) titleType.value = "";
      if (commercialIntent) commercialIntent.value = 0;
      if (writingFitScore) writingFitScore.value = 0;
      if (ctaPresent) ctaPresent.checked = false;
      if (faqStructure) faqStructure.checked = false;
    }

    function clearCollectedImageDetail() {
      const url = qs("#imageUrlView");
      if (url) url.value = "";
      const preview = qs("#imagePreview");
      if (preview) preview.removeAttribute("src");
      const category = qs("#imageCategory");
      const mood = qs("#imageMood");
      const imageType = qs("#imageType");
      const quality = qs("#imageQuality");
      const commercialIntent = qs("#imageCommercialIntent");
      const keywordRelevanceScore = qs("#imageKeywordRelevanceScore");
      const thumb = qs("#imageThumb");
      const textOverlay = qs("#imageTextOverlay");
      const thumbnailScore = qs("#imageThumbnailScore");
      const subjectTags = qs("#imageSubjectTags");
      if (category) category.value = "";
      if (mood) mood.value = "";
      if (imageType) imageType.value = "";
      if (quality) quality.value = 3;
      if (commercialIntent) commercialIntent.value = 0;
      if (keywordRelevanceScore) keywordRelevanceScore.value = 0;
      if (thumb) thumb.checked = false;
      if (textOverlay) textOverlay.checked = false;
      if (thumbnailScore) thumbnailScore.value = 0;
      if (subjectTags) subjectTags.value = "";
    }

    function closeCollectedDetailModal() {
      const root = qs("#collectedDetailModal");
      if (!root) return;
      root.classList.add("hidden");
      root.setAttribute("aria-hidden", "true");
    }

    function openCollectedDetailModal(type, title) {
      const root = qs("#collectedDetailModal");
      const textBody = qs("#collectedDetailTextBody");
      const imageBody = qs("#collectedDetailImageBody");
      const titleNode = qs("#collectedDetailTitle");
      if (!root || !textBody || !imageBody || !titleNode) return;
      titleNode.textContent = title || "상세 보기";
      textBody.classList.toggle("hidden", type !== "content");
      imageBody.classList.toggle("hidden", type !== "image");
      root.classList.remove("hidden");
      root.setAttribute("aria-hidden", "false");
    }

    function renderSimplePager(wrapId, page, total, pageSize, onPageChange) {
      const wrap = qs(`#${wrapId}`);
      if (!wrap) return;
      const totalCount = Number(total || 0);
      const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
      const current = Math.min(Math.max(1, Number(page || 1)), totalPages);
      wrap.innerHTML = "";

      const prevBtn = document.createElement("button");
      prevBtn.type = "button";
      prevBtn.className = "btn ghost";
      prevBtn.textContent = "이전";
      prevBtn.disabled = current <= 1;
      prevBtn.addEventListener("click", () => onPageChange(current - 1));

      const nextBtn = document.createElement("button");
      nextBtn.type = "button";
      nextBtn.className = "btn ghost";
      nextBtn.textContent = "다음";
      nextBtn.disabled = current >= totalPages;
      nextBtn.addEventListener("click", () => onPageChange(current + 1));

      const info = document.createElement("span");
      info.className = "pager-info";
      info.textContent = `총 ${totalCount}개 / ${current} / ${totalPages} 페이지`;

      wrap.appendChild(prevBtn);
      wrap.appendChild(nextBtn);
      wrap.appendChild(info);
    }

    function getFilteredContentRows() {
      const sortMode = String(qs("#collectedContentSort")?.value || "created_desc");
      const minFit = Number(qs("#collectedFitFilter")?.value || 0);
      const hideCommercial = !!qs("#collectedHideCommercial")?.checked;
      const search = String(qs("#collectedContentSearch")?.value || "").trim().toLowerCase();
      const structureFilter = String(qs("#collectedStructureFilter")?.value || "").trim().toLowerCase();
      const labelStatusFilter = String(qs("#collectedLabelStatusFilter")?.value || "").trim().toLowerCase();
      let rows = [...(state.contentRows || [])];
      rows = rows.filter((row) => {
        const summary = row.label_summary || {};
        const fit = Number(summary.writing_fit_score || 0);
        const commercial = Number(summary.commercial_intent || 0);
        const structureType = String(summary.structure_type || "").toLowerCase();
        const labelStatus = String(row.label_status || "").toLowerCase();
        if (fit < minFit) return false;
        if (hideCommercial && commercial >= 4) return false;
        if (structureFilter && structureType !== structureFilter) return false;
        if (labelStatusFilter && labelStatus !== labelStatusFilter) return false;
        if (search) {
          const haystack = `${row.keyword || ""} ${row.title || ""} ${row.body_text || ""}`.toLowerCase();
          if (!haystack.includes(search)) return false;
        }
        return true;
      });
      if (sortMode === "writing_fit_desc") {
        rows.sort((a, b) => {
          const sa = a.label_summary || {};
          const sb = b.label_summary || {};
          return (
            Number(sb.writing_fit_score || 0) - Number(sa.writing_fit_score || 0)
            || Number(sb.quality_score || 0) - Number(sa.quality_score || 0)
            || Number(sa.commercial_intent || 0) - Number(sb.commercial_intent || 0)
            || String(b.created_at || "").localeCompare(String(a.created_at || ""))
          );
        });
      } else if (sortMode === "quality_desc") {
        rows.sort((a, b) => {
          const sa = a.label_summary || {};
          const sb = b.label_summary || {};
          return (
            Number(sb.quality_score || 0) - Number(sa.quality_score || 0)
            || Number(sb.writing_fit_score || 0) - Number(sa.writing_fit_score || 0)
            || String(b.created_at || "").localeCompare(String(a.created_at || ""))
          );
        });
      } else {
        rows.sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")));
      }
      return rows;
    }

    function getFilteredImageRows() {
      const thumbOnly = !!qs("#collectedThumbOnly")?.checked;
      const hideTextOverlay = !!qs("#collectedHideTextOverlay")?.checked;
      const search = String(qs("#collectedImageSearch")?.value || "").trim().toLowerCase();
      const labelStatusFilter = String(qs("#collectedImageLabelStatusFilter")?.value || "").trim().toLowerCase();
      let rows = [...(state.imageRows || [])];
      rows = rows.filter((row) => {
        const summary = row.label_summary || {};
        const labelStatus = String(row.label_status || "").toLowerCase();
        if (thumbOnly && !(!!summary.is_thumbnail_candidate || Number(summary.thumbnail_score || 0) >= 60)) return false;
        if (hideTextOverlay && !!summary.text_overlay) return false;
        if (labelStatusFilter && labelStatus !== labelStatusFilter) return false;
        if (search) {
          const haystack = `${row.id || ""} ${row.content_id || ""} ${row.keyword || ""} ${row.content_title || ""} ${row.image_url || ""} ${row.source_url || ""} ${row.local_path || ""}`.toLowerCase();
          if (!haystack.includes(search)) return false;
        }
        return true;
      });
      rows.sort((a, b) => {
        const sa = a.label_summary || {};
        const sb = b.label_summary || {};
        return (
          Number(sb.thumbnail_score || 0) - Number(sa.thumbnail_score || 0)
          || Number(sb.quality_score || 0) - Number(sa.quality_score || 0)
          || Number(!!sb.is_thumbnail_candidate) - Number(!!sa.is_thumbnail_candidate)
        );
      });
      return rows;
    }

    async function loadContentDetail(row) {
      if (!row) {
        clearCollectedContentDetail();
        return;
      }
      const source = qs("#contentSourceUrl");
      if (source) source.value = row.source_url || "";
      setCollectedContentHtml(textToHtml(row.body_text || ""));
      const label = await request(`/api/labels/content?content_id=${row.id}`);
      const tone = qs("#contentTone");
      const sentiment = qs("#contentSentiment");
      const topics = qs("#contentTopics");
      const quality = qs("#contentQuality");
      const structureType = qs("#contentStructureType");
      const titleType = qs("#contentTitleType");
      const commercialIntent = qs("#contentCommercialIntent");
      const writingFitScore = qs("#contentWritingFitScore");
      const ctaPresent = qs("#contentCtaPresent");
      const faqStructure = qs("#contentFaqStructure");
      if (tone) tone.value = label.tone || "";
      if (sentiment) sentiment.value = label.sentiment || "";
      if (topics) topics.value = (label.topics || []).join(",");
      if (quality) quality.value = label.quality_score || 3;
      if (structureType) structureType.value = label.structure_type || "";
      if (titleType) titleType.value = label.title_type || "";
      if (commercialIntent) commercialIntent.value = Number(label.commercial_intent || 0);
      if (writingFitScore) writingFitScore.value = Number(label.writing_fit_score || 0);
      if (ctaPresent) ctaPresent.checked = !!label.cta_present;
      if (faqStructure) faqStructure.checked = !!label.faq_structure;
    }

    async function loadImageDetail(row) {
      if (!row) {
        clearCollectedImageDetail();
        return;
      }
      const url = qs("#imageUrlView");
      if (url) url.value = row.image_url || "";
      const preview = qs("#imagePreview");
      if (preview) preview.src = row.local_url || row.image_url || "";
      const label = await request(`/api/labels/image?image_id=${row.id}`);
      const category = qs("#imageCategory");
      const mood = qs("#imageMood");
      const imageType = qs("#imageType");
      const quality = qs("#imageQuality");
      const commercialIntent = qs("#imageCommercialIntent");
      const keywordRelevanceScore = qs("#imageKeywordRelevanceScore");
      const thumb = qs("#imageThumb");
      const textOverlay = qs("#imageTextOverlay");
      const thumbnailScore = qs("#imageThumbnailScore");
      const subjectTags = qs("#imageSubjectTags");
      if (category) category.value = label.category || "";
      if (mood) mood.value = label.mood || "";
      if (imageType) imageType.value = label.image_type || "";
      if (quality) quality.value = label.quality_score || 3;
      if (commercialIntent) commercialIntent.value = Number(label.commercial_intent || 0);
      if (keywordRelevanceScore) keywordRelevanceScore.value = Number(label.keyword_relevance_score || 0);
      if (thumb) thumb.checked = !!label.is_thumbnail_candidate;
      if (textOverlay) textOverlay.checked = !!label.text_overlay;
      if (thumbnailScore) thumbnailScore.value = Number(label.thumbnail_score || 0);
      if (subjectTags) subjectTags.value = Array.isArray(label.subject_tags) ? label.subject_tags.join(", ") : "";
    }

    async function openContentDetail(row) {
      state.selectedContentId = row?.id || null;
      state.selectedContentRow = row || null;
      openCollectedDetailModal("content", `텍스트 상세 #${row?.id || "-"}`);
      ensureCollectedContentEditor();
      await loadContentDetail(row);
    }

    async function openImageDetail(row) {
      state.selectedImageId = row?.id || null;
      state.selectedImageRow = row || null;
      openCollectedDetailModal("image", `이미지 상세 #${row?.id || "-"}`);
      await loadImageDetail(row);
    }

    function renderCollectedContentsBoard() {
      const tbody = qs("#collectedContentTable tbody");
      if (!tbody) return;
      tbody.innerHTML = "";
      const rows = getFilteredContentRows();

      if (!rows.length) {
        const tr = document.createElement("tr");
        tr.innerHTML = "<td colspan='7'>조건에 맞는 수집 텍스트 없음</td>";
        tbody.appendChild(tr);
        return;
      }

      rows.forEach((r) => {
        const labelStatus = String(r.label_status || "pending");
        const statusClass = labelStatus === "completed"
          ? "ok"
          : (labelStatus.includes("done") ? "warn" : "neutral");
        const summary = r.label_summary || {};
        const fitScore = Number(summary.writing_fit_score || 0);
        const commercialIntent = Number(summary.commercial_intent || 0);
        const qualityScore = Number(summary.quality_score || 0);
        const fitClass = fitScore >= 4 ? "ok" : (fitScore >= 2 ? "warn" : "neutral");
        const commercialClass = commercialIntent >= 4 ? "fail" : (commercialIntent >= 2 ? "warn" : "ok");
        const metaBadges = [
          qualityScore ? `<span class="badge-status neutral">품질 ${qualityScore}</span>` : "",
          fitScore ? `<span class="badge-status ${fitClass}">작성 ${fitScore}</span>` : "",
          commercialIntent ? `<span class="badge-status ${commercialClass}">광고 ${commercialIntent}</span>` : "",
          summary.structure_type ? `<span class="badge-status neutral">${escapeHtml(summary.structure_type)}</span>` : "",
        ].filter(Boolean).join(" ");
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${r.id}</td>
          <td>
            <div>${escapeHtml(r.title || "(제목 없음)")}</div>
            <div class="label-badge-row">${metaBadges || "<span class='badge-status neutral'>라벨 요약 없음</span>"}</div>
          </td>
          <td>${escapeHtml(r.keyword || "-")}</td>
          <td>${escapeHtml(r.channel || "-")}</td>
          <td><span class="badge-status ${statusClass}">${escapeHtml(labelStatus)}</span></td>
          <td>${fmt(r.created_at)}</td>
          <td><button type="button" class="btn ghost">상세/라벨</button></td>
        `;
        const openBtn = tr.querySelector("button");
        if (openBtn) {
          openBtn.addEventListener("click", () => {
            openContentDetail(r).catch((e) => showAlert(String(e), "오류", "error"));
          });
        }
        tbody.appendChild(tr);
      });
    }

    function renderCollectedImageGallery() {
      const wrap = qs("#collectedImageGallery");
      if (!wrap) return;
      wrap.innerHTML = "";
      const rows = getFilteredImageRows();

      if (!rows.length) {
        wrap.innerHTML = "<div class='hint'>조건에 맞는 수집 이미지 없음</div>";
        return;
      }

      rows.forEach((r) => {
        const labelStatus = String(r.label_status || "pending");
        const statusClass = labelStatus === "completed"
          ? "ok"
          : (labelStatus.includes("done") ? "warn" : "neutral");
        const summary = r.label_summary || {};
        const thumbnailScore = Number(summary.thumbnail_score || 0);
        const qualityScore = Number(summary.quality_score || 0);
        const relevanceScore = Number(summary.keyword_relevance_score || 0);
        const commercialIntent = Number(summary.commercial_intent || 0);
        const thumbClass = summary.is_thumbnail_candidate ? "ok" : (thumbnailScore >= 40 ? "warn" : "neutral");
        const relevanceClass = relevanceScore >= 70 ? "ok" : (relevanceScore >= 40 ? "warn" : "neutral");
        const commercialClass = commercialIntent >= 4 ? "fail" : (commercialIntent >= 2 ? "warn" : "ok");
        const card = document.createElement("article");
        card.className = "collected-gallery-item";
        const src = r.local_url || r.image_url || "";
        card.innerHTML = `
          <img class="collected-gallery-thumb" src="${escapeHtml(src)}" alt="image-${r.id}" />
          <div class="collected-gallery-body">
            <div class="collected-gallery-meta">#${r.id} | content_id=${r.content_id || "-"}</div>
            <div class="collected-gallery-meta">${escapeHtml(r.keyword || "-")}</div>
            <div class="collected-gallery-meta">${escapeHtml(r.content_title || "(원문 제목 없음)")}</div>
            <div class="collected-gallery-meta">라벨: <span class="badge-status ${statusClass}">${escapeHtml(labelStatus)}</span> | 시도 ${Number(r.label_attempt_count || 0)}</div>
            <div class="collected-gallery-meta label-badge-row">
              ${qualityScore ? `<span class="badge-status neutral">품질 ${qualityScore}</span>` : ""}
              ${thumbnailScore ? `<span class="badge-status ${thumbClass}">썸네일 ${thumbnailScore}</span>` : ""}
              ${relevanceScore ? `<span class="badge-status ${relevanceClass}">적합 ${relevanceScore}</span>` : ""}
              ${commercialIntent ? `<span class="badge-status ${commercialClass}">광고 ${commercialIntent}</span>` : ""}
              ${summary.image_type ? `<span class="badge-status neutral">${escapeHtml(summary.image_type)}</span>` : ""}
              ${summary.text_overlay ? `<span class="badge-status warn">텍스트 포함</span>` : ""}
            </div>
            <div class="collected-gallery-meta">${escapeHtml(r.image_url || "-")}</div>
            <div class="collected-gallery-actions"><button type="button" class="btn ghost">상세/라벨</button></div>
          </div>
        `;
        const openBtn = card.querySelector("button");
        if (openBtn) {
          openBtn.addEventListener("click", () => {
            openImageDetail(r).catch((e) => showAlert(String(e), "오류", "error"));
          });
        }
        wrap.appendChild(card);
      });
    }

    async function refreshCollectedDataSection() {
      const contentSearch = encodeURIComponent(String(qs("#collectedContentSearch")?.value || "").trim());
      const structureFilter = encodeURIComponent(String(qs("#collectedStructureFilter")?.value || "").trim());
      const labelStatusFilter = encodeURIComponent(String(qs("#collectedLabelStatusFilter")?.value || "").trim());
      const contentQs = `page=${state.contentPage}&page_size=${state.contentPageSize}&search=${contentSearch}&structure_type=${structureFilter}&label_status=${labelStatusFilter}`;
      const imageSearch = encodeURIComponent(String(qs("#collectedImageSearch")?.value || "").trim());
      const imageStatus = encodeURIComponent(String(qs("#collectedImageLabelStatusFilter")?.value || "").trim());
      const imageQs = `page=${state.imagePage}&page_size=${state.imagePageSize}&search=${imageSearch}&label_status=${imageStatus}`;
      const [contents, images] = await Promise.all([
        request(`/api/collected/contents?${contentQs}`),
        request(`/api/collected/images?${imageQs}`),
      ]);

      state.contentRows = Array.isArray(contents?.items) ? contents.items : [];
      state.imageRows = Array.isArray(images?.items) ? images.items : [];
      state.contentTotal = Number(contents?.total || 0);
      state.imageTotal = Number(images?.total || 0);
      state.contentPage = Number(contents?.page || state.contentPage || 1);
      state.imagePage = Number(images?.page || state.imagePage || 1);

      renderCollectedContentsBoard();
      renderCollectedImageGallery();

      renderSimplePager("collectedContentPager", state.contentPage, state.contentTotal, state.contentPageSize, (nextPage) => {
        state.contentPage = nextPage;
        refreshCollectedDataSection().catch((e) => showAlert(String(e), "오류", "error"));
      });

      renderSimplePager("collectedImagePager", state.imagePage, state.imageTotal, state.imagePageSize, (nextPage) => {
        state.imagePage = nextPage;
        refreshCollectedDataSection().catch((e) => showAlert(String(e), "오류", "error"));
      });
    }

    function switchCollectedTab(tab) {
      state.collectedTab = tab === "image" ? "image" : "text";
      const textPane = qs("#collectedTextPane");
      const imagePane = qs("#collectedImagePane");
      const textBtn = qs("#tabTextBtn");
      const imageBtn = qs("#tabImageBtn");

      if (state.collectedTab === "image") {
        textPane?.classList.add("hidden");
        imagePane?.classList.remove("hidden");
        textBtn?.classList.add("ghost");
        imageBtn?.classList.remove("ghost");
        return;
      }

      imagePane?.classList.add("hidden");
      textPane?.classList.remove("hidden");
      imageBtn?.classList.add("ghost");
      textBtn?.classList.remove("ghost");
    }

    async function saveContentLabel() {
      if (!state.selectedContentId) return showAlert("텍스트를 선택하세요.");
      const topicsNode = qs("#contentTopics");
      const toneNode = qs("#contentTone");
      const sentimentNode = qs("#contentSentiment");
      const qualityNode = qs("#contentQuality");
      const structureTypeNode = qs("#contentStructureType");
      const titleTypeNode = qs("#contentTitleType");
      const commercialIntentNode = qs("#contentCommercialIntent");
      const writingFitScoreNode = qs("#contentWritingFitScore");
      const ctaPresentNode = qs("#contentCtaPresent");
      const faqStructureNode = qs("#contentFaqStructure");

      const topics = String(topicsNode?.value || "")
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean);

      await request("/api/labels/content", {
        method: "POST",
        body: JSON.stringify({
          content_id: state.selectedContentId,
          tone: toneNode?.value || "",
          sentiment: sentimentNode?.value || "",
          topics,
          quality_score: Number(qualityNode?.value || 3),
          structure_type: structureTypeNode?.value || "",
          title_type: titleTypeNode?.value || "",
          commercial_intent: Number(commercialIntentNode?.value || 0),
          writing_fit_score: Number(writingFitScoreNode?.value || 0),
          cta_present: !!ctaPresentNode?.checked,
          faq_structure: !!faqStructureNode?.checked,
        }),
      });
      showAlert("텍스트 라벨이 저장되었습니다.", "성공", "success");
    }

    async function saveImageLabel() {
      if (!state.selectedImageId) return showAlert("이미지를 선택하세요.");
      const categoryNode = qs("#imageCategory");
      const moodNode = qs("#imageMood");
      const imageTypeNode = qs("#imageType");
      const qualityNode = qs("#imageQuality");
      const commercialIntentNode = qs("#imageCommercialIntent");
      const keywordRelevanceScoreNode = qs("#imageKeywordRelevanceScore");
      const thumbNode = qs("#imageThumb");
      const textOverlayNode = qs("#imageTextOverlay");
      const thumbnailScoreNode = qs("#imageThumbnailScore");
      const subjectTagsNode = qs("#imageSubjectTags");

      await request("/api/labels/image", {
        method: "POST",
        body: JSON.stringify({
          image_id: state.selectedImageId,
          category: categoryNode?.value || "",
          mood: moodNode?.value || "",
          image_type: imageTypeNode?.value || "",
          subject_tags: String(subjectTagsNode?.value || "").split(",").map((x) => x.trim()).filter(Boolean),
          commercial_intent: Number(commercialIntentNode?.value || 0),
          keyword_relevance_score: Number(keywordRelevanceScoreNode?.value || 0),
          quality_score: Number(qualityNode?.value || 3),
          is_thumbnail_candidate: !!thumbNode?.checked,
          text_overlay: !!textOverlayNode?.checked,
          thumbnail_score: Number(thumbnailScoreNode?.value || 0),
        }),
      });
      showAlert("이미지 라벨이 저장되었습니다.", "성공", "success");
    }

    function bindCollectedUi() {
      if (state.collectedUiBound) return;
      state.collectedUiBound = true;

      qs("#tabTextBtn")?.addEventListener("click", () => switchCollectedTab("text"));
      qs("#tabImageBtn")?.addEventListener("click", () => switchCollectedTab("image"));
      qs("#collectedRefreshBtn")?.addEventListener("click", () => refreshCollectedDataSection().catch((e) => showAlert(String(e), "오류", "error")));
      ["#collectedContentSort", "#collectedFitFilter", "#collectedHideCommercial", "#collectedThumbOnly", "#collectedHideTextOverlay", "#collectedStructureFilter", "#collectedLabelStatusFilter", "#collectedImageLabelStatusFilter"].forEach((selector) => {
        qs(selector)?.addEventListener("change", () => {
          if (["#collectedThumbOnly", "#collectedHideTextOverlay", "#collectedImageLabelStatusFilter"].includes(selector)) {
            state.imagePage = 1;
            refreshCollectedDataSection().catch((e) => showAlert(String(e), "오류", "error"));
            return;
          }
          state.contentPage = 1;
          refreshCollectedDataSection().catch((e) => showAlert(String(e), "오류", "error"));
        });
      });
      qs("#collectedContentSearch")?.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        state.contentPage = 1;
        refreshCollectedDataSection().catch((err) => showAlert(String(err), "오류", "error"));
      });
      qs("#collectedContentSearch")?.addEventListener("input", () => {
        if (String(qs("#collectedContentSearch")?.value || "").trim()) {
          renderCollectedContentsBoard();
          return;
        }
        state.contentPage = 1;
        refreshCollectedDataSection().catch((err) => showAlert(String(err), "오류", "error"));
      });
      qs("#collectedImageSearch")?.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        state.imagePage = 1;
        refreshCollectedDataSection().catch((err) => showAlert(String(err), "오류", "error"));
      });
      qs("#collectedImageSearch")?.addEventListener("input", () => {
        if (String(qs("#collectedImageSearch")?.value || "").trim()) {
          renderCollectedImageGallery();
          return;
        }
        state.imagePage = 1;
        refreshCollectedDataSection().catch((err) => showAlert(String(err), "오류", "error"));
      });

      qs("#contentLabelSaveBtn")?.addEventListener("click", () => saveContentLabel().catch((e) => showAlert(String(e), "오류", "error")));
      qs("#imageLabelSaveBtn")?.addEventListener("click", () => saveImageLabel().catch((e) => showAlert(String(e), "오류", "error")));

      qs("#collectedDetailBackdrop")?.addEventListener("click", closeCollectedDetailModal);
      qs("#collectedDetailCloseBtn")?.addEventListener("click", closeCollectedDetailModal);
      qs("#collectedDetailCloseX")?.addEventListener("click", closeCollectedDetailModal);

      document.addEventListener("keydown", (e) => {
        if (e.key !== "Escape") return;
        const root = qs("#collectedDetailModal");
        if (!root || root.classList.contains("hidden")) return;
        closeCollectedDetailModal();
      });
    }

    return {
      ensureWriterEditor,
      setWriterContentHtml,
      getWriterContentHtml,
      switchCollectedTab,
      refreshCollectedDataSection,
      bindCollectedUi,
    };
  }

  window.createCollectedDataModule = createCollectedDataModule;
})();
