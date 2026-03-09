(() => {
  function createCommonModule(ctx) {
    const { qs } = ctx || {};

    function selectValueIfExists(selectEl, value) {
      if (!selectEl) return false;
      const target = String(value || "");
      if (!target) return false;
      const found = [...selectEl.options].some((o) => String(o.value) === target);
      if (!found) return false;
      selectEl.value = target;
      return true;
    }

    function fmt(v) {
      if (!v) return "-";
      return String(v).replace("T", " ").slice(0, 19);
    }

    function yn(v) {
      return v ? "Y" : "N";
    }

    async function request(url, options = {}) {
      const method = String(options.method || "GET").toUpperCase();
      const res = await fetch(url, {
        cache: method === "GET" ? "default" : "no-store",
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        ...options,
      });
      let data = null;
      try {
        data = await res.json();
      } catch (_e) {
        data = null;
      }
      if (!res.ok) {
        const err = new Error((data && data.error) || `HTTP ${res.status}`);
        err.status = res.status;
        err.code = String((data && data.error_code) || "");
        err.fields = (data && data.fields && typeof data.fields === "object") ? data.fields : {};
        err.requestId = String((data && data.request_id) || res.headers.get("X-Request-Id") || "");
        if (err.code || err.requestId) {
          console.warn("API request failed", {
            url,
            status: err.status,
            errorCode: err.code,
            requestId: err.requestId,
          });
        }
        throw err;
      }
      return data;
    }

    function clearFieldError(selector) {
      const input = qs(selector);
      if (!input) return;
      input.classList.remove("input-error");
      input.removeAttribute("title");
    }

    function setFieldError(selector, message) {
      const input = qs(selector);
      if (!input) return;
      input.classList.add("input-error");
      input.setAttribute("title", String(message || ""));
    }

    function clearFieldErrors(selectors = []) {
      (selectors || []).forEach((sel) => clearFieldError(sel));
    }

    function applyFieldErrors(fieldErrors, fieldSelectorMap, hintSelector) {
      const map = fieldErrors && typeof fieldErrors === "object" ? fieldErrors : {};
      const lines = [];
      Object.entries(map).forEach(([field, message]) => {
        const sel = fieldSelectorMap[field];
        if (sel) setFieldError(sel, String(message || ""));
        lines.push(`${field}: ${String(message || "")}`);
      });
      const hint = qs(hintSelector);
      if (hint) hint.textContent = lines.length ? `검증 오류: ${lines.join(" / ")}` : "-";
    }

    function syncSelectOptions(select, rows, toValue, toLabel, selectedValue) {
      if (!select) return;
      const values = rows.map((row) => String(toValue(row)));
      const labels = rows.map((row) => String(toLabel(row)));
      let changed = select.options.length !== rows.length;
      if (!changed) {
        for (let i = 0; i < rows.length; i += 1) {
          const opt = select.options[i];
          if (!opt || opt.value !== values[i] || opt.text !== labels[i]) {
            changed = true;
            break;
          }
        }
      }
      if (changed) {
        const scrollTop = select.scrollTop;
        select.innerHTML = "";
        rows.forEach((row, idx) => {
          const opt = document.createElement("option");
          opt.value = values[idx];
          opt.textContent = labels[idx];
          select.appendChild(opt);
        });
        select.scrollTop = scrollTop;
      }
      if (selectedValue != null) {
        select.value = String(selectedValue);
      }
    }

    return {
      selectValueIfExists,
      fmt,
      yn,
      request,
      clearFieldError,
      setFieldError,
      clearFieldErrors,
      applyFieldErrors,
      syncSelectOptions,
    };
  }

  window.createCommonModule = createCommonModule;
})();
