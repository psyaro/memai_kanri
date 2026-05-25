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
});
