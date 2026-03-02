(() => {
  function createDialogModule(ctx) {
    const { qs } = ctx || {};
    let appModalResolver = null;

    function modalEscape(value) {
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function closeAppModal(result) {
      const root = qs("#appModal");
      if (!root) return;
      root.classList.add("hidden");
      root.setAttribute("aria-hidden", "true");
      const resolver = appModalResolver;
      appModalResolver = null;
      if (resolver) resolver(result);
    }

    function bindAppModalKeydown() {
      if (window.__appModalBound) return;
      window.__appModalBound = true;
      document.addEventListener("keydown", (e) => {
        const root = qs("#appModal");
        if (!root || root.classList.contains("hidden")) return;
        if (e.key === "Escape") {
          e.preventDefault();
          closeAppModal(false);
        }
      });
    }

    function showModalDialog({ title = "알림", message = "", kind = "alert", variant = "info" } = {}) {
      bindAppModalKeydown();
      const root = qs("#appModal");
      const titleNode = qs("#appModalTitle");
      const messageNode = qs("#appModalMessage");
      const okBtn = qs("#appModalOk");
      const cancelBtn = qs("#appModalCancel");
      const backdrop = qs("#appModalBackdrop");
      const closeBtn = qs("#appModalClose");
      if (!root || !titleNode || !messageNode || !okBtn || !cancelBtn || !backdrop || !closeBtn) {
        if (kind === "confirm") return Promise.resolve(window.confirm(`${title}\n\n${message}`));
        window.alert(`${title}\n\n${message}`);
        return Promise.resolve(true);
      }

      titleNode.textContent = title;
      messageNode.innerHTML = String(message || "")
        .split("\n")
        .map((line) => modalEscape(line))
        .join("<br>");
      root.setAttribute("data-variant", variant || "info");
      cancelBtn.classList.toggle("hidden", kind !== "confirm");
      okBtn.textContent = kind === "confirm" ? "확인" : "닫기";

      root.classList.remove("hidden");
      root.setAttribute("aria-hidden", "false");

      return new Promise((resolve) => {
        appModalResolver = resolve;
        const onOk = () => closeAppModal(true);
        const onCancel = () => closeAppModal(false);
        const onBackdrop = (ev) => {
          if (ev.target === backdrop) closeAppModal(false);
        };

        okBtn.onclick = onOk;
        cancelBtn.onclick = onCancel;
        closeBtn.onclick = onCancel;
        backdrop.onclick = onBackdrop;
      });
    }

    function showAlert(message, title = "알림", variant = "info") {
      return showModalDialog({ title, message, kind: "alert", variant });
    }

    function showConfirm(message, title = "확인", variant = "warn") {
      return showModalDialog({ title, message, kind: "confirm", variant });
    }

    function showActionAlert(entity, action, ok = true, detail = "") {
      const actionMap = {
        create: "추가",
        update: "수정",
        delete: "삭제",
        save: "저장",
        run: "실행",
      };
      const label = actionMap[action] || action || "처리";
      if (ok) {
        const message = detail ? `${entity} ${label} 성공\n${detail}` : `${entity} ${label} 성공`;
        return showAlert(message, "완료", "success");
      }
      const message = detail ? `${entity} ${label} 실패\n${detail}` : `${entity} ${label} 실패`;
      return showAlert(message, "오류", "error");
    }

    return {
      showAlert,
      showConfirm,
      showActionAlert,
    };
  }

  window.createDialogModule = createDialogModule;
})();
