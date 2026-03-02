(() => {
  function createCollectionUiModule(ctx) {
    const { qs, state } = ctx || {};

    function buildCollectCategories(rows) {
      const map = new Map();
      rows.forEach((r) => {
        const key = r.category_id == null ? "__none__" : `cat_${r.category_id}`;
        if (map.has(key)) return;
        map.set(key, {
          key,
          id: r.category_id ?? null,
          name: r.category_name || "미분류",
        });
      });
      return [...map.values()].sort((a, b) => String(a.name).localeCompare(String(b.name), "ko"));
    }

    function closeCollectSelectMenus() {
      const categoryBtn = qs("#collectCategorySelectBtn");
      const categoryList = qs("#collectCategorySelectList");
      const keywordBtn = qs("#collectKeywordSelectBtn");
      const keywordList = qs("#collectKeywordSelectList");
      if (categoryList) categoryList.classList.add("hidden");
      if (keywordList) keywordList.classList.add("hidden");
      if (categoryBtn) {
        categoryBtn.classList.remove("open");
        categoryBtn.setAttribute("aria-expanded", "false");
      }
      if (keywordBtn) {
        keywordBtn.classList.remove("open");
        keywordBtn.setAttribute("aria-expanded", "false");
      }
    }

    function toggleCollectSelectMenu(which) {
      const categoryBtn = qs("#collectCategorySelectBtn");
      const categoryList = qs("#collectCategorySelectList");
      const keywordBtn = qs("#collectKeywordSelectBtn");
      const keywordList = qs("#collectKeywordSelectList");
      const targetList = which === "category" ? categoryList : keywordList;
      const targetBtn = which === "category" ? categoryBtn : keywordBtn;
      if (!targetList || !targetBtn) return;

      const willOpen = targetList.classList.contains("hidden");
      closeCollectSelectMenus();
      if (!willOpen) return;

      targetList.classList.remove("hidden");
      targetBtn.classList.add("open");
      targetBtn.setAttribute("aria-expanded", "true");
    }

    function renderCollectCategorySelect() {
      const label = qs("#collectCategorySelectLabel");
      const list = qs("#collectCategorySelectList");
      if (!label || !list) return;
      list.innerHTML = "";
      if (!state.collectCategories.length) {
        label.textContent = "카테고리 없음";
        list.innerHTML = "<li class='choice-empty'>카테고리 없음</li>";
        return;
      }
      if (!state.selectedCollectCategoryKey || !state.collectCategories.some((c) => c.key === state.selectedCollectCategoryKey)) {
        state.selectedCollectCategoryKey = state.collectCategories[0].key;
      }
      const selected = state.collectCategories.find((c) => c.key === state.selectedCollectCategoryKey);
      label.textContent = selected ? selected.name : "카테고리 선택";

      state.collectCategories.forEach((c) => {
        const li = document.createElement("li");
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "custom-select-option";
        btn.textContent = c.name;
        if (state.selectedCollectCategoryKey === c.key) btn.classList.add("selected");
        btn.addEventListener("click", () => {
          state.selectedCollectCategoryKey = c.key;
          renderCollectCategorySelect();
          renderCollectKeywordSelect();
          closeCollectSelectMenus();
        });
        li.appendChild(btn);
        list.appendChild(li);
      });
    }

    function renderCollectKeywordSelect() {
      const label = qs("#collectKeywordSelectLabel");
      const list = qs("#collectKeywordSelectList");
      if (!label || !list) return;
      list.innerHTML = "";
      const filtered = state.collectKeywords.filter((r) => {
        const key = r.category_id == null ? "__none__" : `cat_${r.category_id}`;
        return key === state.selectedCollectCategoryKey;
      });
      if (!filtered.length) {
        state.selectedCollectKeywordId = null;
        label.textContent = "키워드 없음";
        list.innerHTML = "<li class='choice-empty'>키워드 없음</li>";
        return;
      }
      if (!state.selectedCollectKeywordId || !filtered.some((r) => r.id === state.selectedCollectKeywordId)) {
        state.selectedCollectKeywordId = filtered[0].id;
      }
      const selected = filtered.find((r) => r.id === state.selectedCollectKeywordId);
      label.textContent = selected ? selected.keyword : "키워드 선택";

      filtered.forEach((r) => {
        const li = document.createElement("li");
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "custom-select-option";
        btn.textContent = r.keyword;
        if (state.selectedCollectKeywordId === r.id) btn.classList.add("selected");
        btn.addEventListener("click", () => {
          state.selectedCollectKeywordId = r.id;
          renderCollectKeywordSelect();
          closeCollectSelectMenus();
        });
        li.appendChild(btn);
        list.appendChild(li);
      });
    }

    function setupCollectionSelectUi() {
      if (state.collectUiBound) return;
      state.collectUiBound = true;
      qs("#collectCategorySelectBtn")?.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleCollectSelectMenu("category");
      });
      qs("#collectKeywordSelectBtn")?.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleCollectSelectMenu("keyword");
      });
      qs("#collectCategorySelectList")?.addEventListener("click", (e) => e.stopPropagation());
      qs("#collectKeywordSelectList")?.addEventListener("click", (e) => e.stopPropagation());
      document.addEventListener("click", () => closeCollectSelectMenus());
    }

    function renderCollectFilters(rows) {
      state.collectKeywords = (rows || []).filter((r) => !r.is_auto_generated);
      state.collectCategories = buildCollectCategories(state.collectKeywords);
      if (!state.collectCategories.length) {
        state.selectedCollectCategoryKey = null;
        state.selectedCollectKeywordId = null;
      } else if (!state.selectedCollectCategoryKey || !state.collectCategories.some((c) => c.key === state.selectedCollectCategoryKey)) {
        state.selectedCollectCategoryKey = state.collectCategories[0].key;
      }
      renderCollectCategorySelect();
      renderCollectKeywordSelect();
    }

    function scopeLabel(scope) {
      if (scope === "all") return "전체 수집";
      if (scope === "related") return "키워드 확장";
      return "체크된 내역만";
    }

    function renderCollectSummary(settings, channels, keywords) {
      const s = settings || {};
      const allChannels = channels || [];
      const selectedChannelCodes = (s.selected_channel_codes || []).map((v) => String(v));
      const totalChannelCount = allChannels.length;
      const selectedChannelCount = selectedChannelCodes.length ? selectedChannelCodes.length : totalChannelCount;

      const allCategoryIds = [...new Set((keywords || []).map((r) => r.category_id).filter((v) => v != null))];
      const selectedCategoryIds = (s.selected_category_ids || []).map((v) => Number(v)).filter((v) => Number.isFinite(v));
      const selectedCategoryCount = selectedCategoryIds.length ? selectedCategoryIds.length : allCategoryIds.length;

      qs("#collectSummaryInterval").textContent = String(s.interval_minutes || "-");
      qs("#collectSummaryMax").textContent = String(s.max_results || "-");
      qs("#collectSummaryTimeout").textContent = String(s.request_timeout || "-");
      qs("#collectSummaryRetry").textContent = String(s.retry_count || "-");
      qs("#collectSummaryScope").textContent = scopeLabel(s.keyword_scope || "selected");
      qs("#collectSummaryNaver").textContent = s.naver_related_sync ? "사용" : "미사용";
      qs("#collectSummaryChannels").textContent = `${selectedChannelCount}/${totalChannelCount}`;
      qs("#collectSummaryCategories").textContent = `${selectedCategoryCount}/${allCategoryIds.length}`;
    }

    return {
      setupCollectionSelectUi,
      renderCollectFilters,
      scopeLabel,
      renderCollectSummary,
    };
  }

  window.createCollectionUiModule = createCollectionUiModule;
})();
