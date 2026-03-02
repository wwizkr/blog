(() => {
  function createShellModule(ctx) {
    const {
      qs,
      state,
      request,
      STORAGE_KEY,
      sectionMap,
      menuNodeToSection,
      sectionToDefaultNode,
    } = ctx || {};

    function applyTheme(theme) {
      document.documentElement.setAttribute("data-theme", theme);
      localStorage.setItem(STORAGE_KEY, theme);
    }

    function getInitialTheme() {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "dark" || saved === "light") return saved;
      return "dark";
    }

    function readSection() {
      const p = new URLSearchParams(location.search).get("section") || "keyword";
      return sectionMap[p] ? p : "keyword";
    }

    function isDesktopEmbed() {
      return new URLSearchParams(location.search).get("embed") === "desktop";
    }

    function readMenuNode() {
      return new URLSearchParams(location.search).get("node") || "";
    }

    function flattenMenuNodes(items, bucket = []) {
      (items || []).forEach((item) => {
        bucket.push(item);
        flattenMenuNodes(item.children || [], bucket);
      });
      return bucket;
    }

    function getMenuNodeById(items, nodeId) {
      if (!nodeId) return null;
      return flattenMenuNodes(items).find((n) => n.id === nodeId) || null;
    }

    function getPrimaryFromNode(nodeId) {
      return String(nodeId || "").split(".")[0] || "";
    }

    function resolveMenuNodeId(section, requestedNodeId, defaultNodeId) {
      if (requestedNodeId && getMenuNodeById(state.menuTree, requestedNodeId)) return requestedNodeId;
      const fromSection = sectionToDefaultNode[section] || "";
      if (fromSection && getMenuNodeById(state.menuTree, fromSection)) return fromSection;
      if (defaultNodeId && getMenuNodeById(state.menuTree, defaultNodeId)) return defaultNodeId;
      const firstLeaf = flattenMenuNodes(state.menuTree).find((n) => !(n.children || []).length);
      return firstLeaf?.id || "";
    }

    function navigateToNode(nodeId) {
      const targetSection = menuNodeToSection[nodeId] || state.section || "keyword";
      const params = new URLSearchParams(location.search);
      params.set("section", targetSection);
      params.set("node", nodeId);
      location.search = `?${params.toString()}`;
    }

    function renderV2Menus() {
      const primaryWrap = qs("#primaryMenu");
      if (!primaryWrap) return;
      primaryWrap.innerHTML = "";
      const primaryId = getPrimaryFromNode(state.menuNodeId);

      (state.menuTree || []).forEach((primary) => {
        const group = document.createElement("div");
        group.className = "menu-group";

        const head = document.createElement("button");
        head.type = "button";
        head.className = "menu-group-head";
        head.textContent = primary.label;
        if (primary.id === primaryId) head.classList.add("active");
        head.addEventListener("click", () => {
          const firstChild = (primary.children || [])[0];
          navigateToNode(firstChild?.id || primary.id);
        });
        group.appendChild(head);

        const body = document.createElement("div");
        body.className = "menu-group-body";
        if (primary.id !== primaryId) body.classList.add("hidden");

        (primary.children || []).forEach((node) => {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "menu-btn";
          btn.textContent = node.label;
          if (node.id === state.menuNodeId) btn.classList.add("active");
          btn.addEventListener("click", () => navigateToNode(node.id));
          body.appendChild(btn);
        });

        group.appendChild(body);
        primaryWrap.appendChild(group);
      });

      const currentNode = getMenuNodeById(state.menuTree, state.menuNodeId);
      if (currentNode) {
        const title = qs("#sectionTitle");
        if (title) title.textContent = currentNode.label;
      }
    }

    async function initV2Menus() {
      try {
        const payload = await request("/api/v2/menu");
        state.menuTree = payload.items || [];
        state.menuNodeId = resolveMenuNodeId(readSection(), readMenuNode(), payload.default_node_id || "");
        renderV2Menus();
      } catch (_err) {
        state.menuTree = [];
      }
    }

    function setupSectionShell() {
      state.section = readSection();
      qs("#sectionTitle").textContent = sectionMap[state.section]?.title || "메뉴";

      [
        "#dashboardSection", "#keywordSection", "#collectionSection", "#collectedDataSection", "#labelingSection",
        "#writerRunSection", "#writerResultSection", "#personaSection", "#templateSection", "#aiProviderSection", "#publisherSection",
        "#collectSettingsSection", "#labelSettingsSection", "#writerSettingsSection", "#publishSettingsSection", "#monitorSection", "#settingsSection", "#placeholderSection",
      ].forEach((id) => qs(id)?.classList.add("hidden"));

      const map = {
        dashboard: "#dashboardSection",
        keyword: "#keywordSection",
        collection: "#collectionSection",
        collected_data: "#collectedDataSection",
        labeling: "#labelingSection",
        writer_run: "#writerRunSection",
        writer_result: "#writerResultSection",
        persona: "#personaSection",
        template: "#templateSection",
        ai_provider: "#aiProviderSection",
        publisher: "#publisherSection",
        collect_settings: "#collectSettingsSection",
        label_settings: "#labelSettingsSection",
        writer_settings: "#writerSettingsSection",
        publish_settings: "#publishSettingsSection",
        monitor: "#monitorSection",
        settings: "#settingsSection",
      };

      const target = map[state.section];
      if (target) {
        qs(target)?.classList.remove("hidden");
        qs("#relatedLimitBadge")?.classList.toggle("hidden", state.section !== "keyword");
        return state.section;
      }

      qs("#placeholderSection")?.classList.remove("hidden");
      qs("#placeholderTitle").textContent = sectionMap[state.section]?.title || "준비 중";
      qs("#placeholderDesc").textContent = sectionMap[state.section]?.desc || "이 메뉴는 웹 UI로 전환 중입니다.";
      qs("#relatedLimitBadge")?.classList.add("hidden");
      return "placeholder";
    }

    return {
      applyTheme,
      getInitialTheme,
      isDesktopEmbed,
      navigateToNode,
      renderV2Menus,
      initV2Menus,
      setupSectionShell,
    };
  }

  window.createShellModule = createShellModule;
})();
