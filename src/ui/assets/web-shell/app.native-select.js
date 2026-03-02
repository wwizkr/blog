(() => {
  function createNativeSelectModule(ctx) {
    const { qsa } = ctx || {};

    const nativeSelectProxyState = {
      bound: false,
      openRoot: null,
      proxies: new Map(),
    };

    function getSelectOptionSignature(select) {
      return [...select.options].map((o) => `${o.value}::${o.text}::${o.disabled ? "1" : "0"}`).join("||");
    }

    function closeNativeSelectProxy(root) {
      if (!root) return;
      const btn = root.querySelector(".custom-select-btn");
      const list = root.querySelector(".custom-select-list");
      list?.classList.add("hidden");
      btn?.classList.remove("open");
      btn?.setAttribute("aria-expanded", "false");
      if (nativeSelectProxyState.openRoot === root) nativeSelectProxyState.openRoot = null;
    }

    function closeAllNativeSelectProxies() {
      if (nativeSelectProxyState.openRoot) closeNativeSelectProxy(nativeSelectProxyState.openRoot);
    }

    function renderNativeSelectProxy(select, force = false) {
      const proxy = nativeSelectProxyState.proxies.get(select);
      if (!proxy) return;
      const signature = getSelectOptionSignature(select);
      const selectedValue = String(select.value || "");
      if (!force && signature === proxy.signature && selectedValue === proxy.value) return;

      proxy.signature = signature;
      proxy.value = selectedValue;
      proxy.list.innerHTML = "";

      const options = [...select.options];
      if (!options.length) {
        proxy.label.textContent = "선택 항목 없음";
        proxy.list.innerHTML = "<li class='choice-empty'>선택 항목 없음</li>";
        return;
      }

      const selected = options.find((o) => o.value === selectedValue) || options[0];
      if (selected && select.value !== selected.value) select.value = selected.value;
      proxy.value = String(select.value || "");
      proxy.label.textContent = selected?.text || "선택";

      options.forEach((opt) => {
        const li = document.createElement("li");
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "custom-select-option";
        btn.textContent = opt.text;
        if (opt.disabled) btn.disabled = true;
        if (String(opt.value) === proxy.value) btn.classList.add("selected");
        btn.addEventListener("click", () => {
          if (opt.disabled) return;
          select.value = String(opt.value);
          select.dispatchEvent(new Event("change", { bubbles: true }));
          renderNativeSelectProxy(select, true);
          closeNativeSelectProxy(proxy.root);
        });
        li.appendChild(btn);
        proxy.list.appendChild(li);
      });
    }

    function ensureNativeSelectProxy(select) {
      if (!select || nativeSelectProxyState.proxies.has(select)) return;

      const parent = select.parentElement;
      if (!parent) return;

      const root = document.createElement("div");
      root.className = "native-select-wrap custom-select";
      if (select.id) root.setAttribute("data-select-id", select.id);

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "custom-select-btn";
      btn.setAttribute("aria-haspopup", "listbox");
      btn.setAttribute("aria-expanded", "false");

      const label = document.createElement("span");
      label.className = "native-select-label";
      label.textContent = "선택";

      const caret = document.createElement("span");
      caret.className = "custom-select-caret";
      caret.textContent = "▾";

      const list = document.createElement("ul");
      list.className = "custom-select-list hidden";
      list.setAttribute("role", "listbox");

      btn.appendChild(label);
      btn.appendChild(caret);

      parent.insertBefore(root, select);
      root.appendChild(select);
      root.appendChild(btn);
      root.appendChild(list);

      select.classList.add("native-select-origin");

      const proxy = { root, btn, label, list, signature: "", value: "" };
      nativeSelectProxyState.proxies.set(select, proxy);

      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const willOpen = list.classList.contains("hidden");
        closeAllNativeSelectProxies();
        if (!willOpen) return;
        renderNativeSelectProxy(select, true);
        list.classList.remove("hidden");
        btn.classList.add("open");
        btn.setAttribute("aria-expanded", "true");
        nativeSelectProxyState.openRoot = root;
      });

      list.addEventListener("click", (e) => e.stopPropagation());
      select.addEventListener("change", () => renderNativeSelectProxy(select, true));

      renderNativeSelectProxy(select, true);
    }

    function setupNativeSelectProxies() {
      qsa("select").forEach((select) => ensureNativeSelectProxy(select));

      if (!nativeSelectProxyState.bound) {
        nativeSelectProxyState.bound = true;
        document.addEventListener("click", () => closeAllNativeSelectProxies());
        window.setInterval(() => {
          nativeSelectProxyState.proxies.forEach((_proxy, select) => renderNativeSelectProxy(select));
        }, 300);
      }
    }

    return {
      setupNativeSelectProxies,
      closeAllNativeSelectProxies,
    };
  }

  window.createNativeSelectModule = createNativeSelectModule;
})();
