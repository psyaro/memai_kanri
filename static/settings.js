document.addEventListener("DOMContentLoaded", () => {
  // チェックボックスと hidden inputの連動（時間帯別・有効）
  document.querySelectorAll(".symptom-form, .add-form").forEach((form) => {
    form.querySelectorAll("input[type=checkbox]").forEach((cb) => {
      const hidden = cb.parentElement.nextElementSibling;
      if (hidden && hidden.type === "hidden") {
        cb.addEventListener("change", () => {
          hidden.disabled = cb.checked;
        });
      }
    });
  });

  // ドラッグ＆ドロップで並び替え
  const list = document.getElementById("symptom-list");
  if (!list) return;

  let dragging = null;

  list.addEventListener("dragstart", (e) => {
    dragging = e.target.closest("li");
    dragging.classList.add("dragging");
  });

  list.addEventListener("dragend", () => {
    if (dragging) dragging.classList.remove("dragging");
    dragging = null;
    saveOrder();
  });

  list.addEventListener("dragover", (e) => {
    e.preventDefault();
    const target = e.target.closest("li");
    if (!target || target === dragging) return;
    const rect = target.getBoundingClientRect();
    const after = e.clientY > rect.top + rect.height / 2;
    list.insertBefore(dragging, after ? target.nextSibling : target);
  });

  list.querySelectorAll("li").forEach((li) => {
    li.draggable = true;
  });

  async function saveOrder() {
    const ids = [...list.querySelectorAll("li")].map((li) => parseInt(li.dataset.id));
    await fetch("/settings/reorder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
  }

  // バックアップ復元（リストア）処理
  const btnRestore = document.getElementById("btn-restore");
  const restoreFileInput = document.getElementById("restore-file-input");
  const restoreStatus = document.getElementById("restore-status");

  if (btnRestore && restoreFileInput) {
    btnRestore.addEventListener("click", async () => {
      const file = restoreFileInput.files[0];
      if (!file) {
        alert("復元するバックアップファイル（.json）を選択してください。");
        return;
      }

      if (!confirm("⚠️ 本当に復元を実行しますか？\n現在アプリに記録されているすべてのデータが一度完全に消去され、選択したファイルの内容で上書きされます。")) {
        return;
      }

      restoreStatus.textContent = "⚡ 復元処理中...";
      restoreStatus.hidden = false;
      restoreStatus.style.color = "#e67e22";
      btnRestore.disabled = true;

      const formData = new FormData();
      formData.append("file", file);

      try {
        const res = await fetch("/api/restore", {
          method: "POST",
          body: formData,
        });

        if (res.ok) {
          restoreStatus.textContent = "✓ 復元が正常に完了しました！自動リロードします...";
          restoreStatus.style.color = "#27ae60";
          setTimeout(() => {
            window.location.reload();
          }, 1500);
        } else {
          const errData = await res.json();
          restoreStatus.textContent = `✗ 復元に失敗しました: ${errData.error || "不正なファイルです"}`;
          restoreStatus.style.color = "#e74c3c";
          btnRestore.disabled = false;
        }
      } catch (err) {
        restoreStatus.textContent = "✗ 通信エラーが発生しました。";
        restoreStatus.style.color = "#e74c3c";
        btnRestore.disabled = false;
      }
    });
  }
});
