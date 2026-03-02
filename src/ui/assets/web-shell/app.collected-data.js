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
      if (tone) tone.value = "";
      if (sentiment) sentiment.value = "";
      if (topics) topics.value = "";
      if (quality) quality.value = 3;
    }

    function clearCollectedImageDetail() {
      const url = qs("#imageUrlView");
      if (url) url.value = "";
      const preview = qs("#imagePreview");
      if (preview) preview.removeAttribute("src");
      const category = qs("#imageCategory");
      const mood = qs("#imageMood");
      const quality = qs("#imageQuality");
      const thumb = qs("#imageThumb");
      if (category) category.value = "";
      if (mood) mood.value = "";
      if (quality) quality.value = 3;
      if (thumb) thumb.checked = false;
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
      if (tone) tone.value = label.tone || "";
      if (sentiment) sentiment.value = label.sentiment || "";
      if (topics) topics.value = (label.topics || []).join(",");
      if (quality) quality.value = label.quality_score || 3;
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
      const quality = qs("#imageQuality");
      const thumb = qs("#imageThumb");
      if (category) category.value = label.category || "";
      if (mood) mood.value = label.mood || "";
      if (quality) quality.value = label.quality_score || 3;
      if (thumb) thumb.checked = !!label.is_thumbnail_candidate;
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

      if (!state.contentRows.length) {
        const tr = document.createElement("tr");
        tr.innerHTML = "<td colspan='6'>수집 텍스트 없음</td>";
        tbody.appendChild(tr);
        return;
      }

      state.contentRows.forEach((r) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${r.id}</td>
          <td>${escapeHtml(r.title || "(제목 없음)")}</td>
          <td>${escapeHtml(r.keyword || "-")}</td>
          <td>${escapeHtml(r.channel || "-")}</td>
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

      if (!state.imageRows.length) {
        wrap.innerHTML = "<div class='hint'>수집 이미지 없음</div>";
        return;
      }

      state.imageRows.forEach((r) => {
        const card = document.createElement("article");
        card.className = "collected-gallery-item";
        const src = r.local_url || r.image_url || "";
        card.innerHTML = `
          <img class="collected-gallery-thumb" src="${escapeHtml(src)}" alt="image-${r.id}" />
          <div class="collected-gallery-body">
            <div class="collected-gallery-meta">#${r.id} | content_id=${r.content_id || "-"}</div>
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
      const contentQs = `page=${state.contentPage}&page_size=${state.contentPageSize}`;
      const imageQs = `page=${state.imagePage}&page_size=${state.imagePageSize}`;
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
        }),
      });
      showAlert("텍스트 라벨이 저장되었습니다.", "성공", "success");
    }

    async function saveImageLabel() {
      if (!state.selectedImageId) return showAlert("이미지를 선택하세요.");
      const categoryNode = qs("#imageCategory");
      const moodNode = qs("#imageMood");
      const qualityNode = qs("#imageQuality");
      const thumbNode = qs("#imageThumb");

      await request("/api/labels/image", {
        method: "POST",
        body: JSON.stringify({
          image_id: state.selectedImageId,
          category: categoryNode?.value || "",
          mood: moodNode?.value || "",
          quality_score: Number(qualityNode?.value || 3),
          is_thumbnail_candidate: !!thumbNode?.checked,
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
