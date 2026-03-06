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
      const panel = root?.querySelector(".app-modal-panel");
      const titleNode = qs("#appModalTitle");
      const badgeNode = qs("#appModalBadge");
      const messageNode = qs("#appModalMessage");
      const actionsNode = qs("#appModalActions");
      const backdrop = qs("#appModalBackdrop");
      if (!root || !panel || !titleNode || !badgeNode || !messageNode || !actionsNode || !backdrop) {
        if (kind === "confirm") return Promise.resolve(window.confirm(`${title}\n\n${message}`));
        window.alert(`${title}\n\n${message}`);
        return Promise.resolve(true);
      }

      titleNode.textContent = title;
      badgeNode.textContent = String(variant || "info").toUpperCase();
      messageNode.innerHTML = String(message || "")
        .split("\n")
        .map((line) => modalEscape(line))
        .join("<br>");
      panel.classList.remove("modal-info", "modal-success", "modal-warn", "modal-error");
      panel.classList.add(`modal-${variant || "info"}`);

      actionsNode.innerHTML = "";
      const okBtn = document.createElement("button");
      okBtn.type = "button";
      okBtn.className = "btn";
      okBtn.textContent = kind === "confirm" ? "확인" : "닫기";
      actionsNode.appendChild(okBtn);
      let cancelBtn = null;
      if (kind === "confirm") {
        cancelBtn = document.createElement("button");
        cancelBtn.type = "button";
        cancelBtn.className = "btn ghost";
        cancelBtn.textContent = "취소";
        actionsNode.appendChild(cancelBtn);
      }

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
        if (cancelBtn) cancelBtn.onclick = onCancel;
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
