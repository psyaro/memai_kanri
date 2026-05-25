document.addEventListener("DOMContentLoaded", () => {
  const dateInput = document.getElementById("date-input");
  const form = document.getElementById("record-form");
  const saveMsg = document.getElementById("save-msg");
  const noteInput = document.getElementById("note-input");

  restoreExisting(EXISTING);

  // スコアボタン：選択済みを再タップで未入力に戻す
  document.querySelectorAll(".score-buttons").forEach((group) => {
    group.addEventListener("click", (e) => {
      const btn = e.target.closest(".score-btn");
      if (!btn) return;
      const isSelected = btn.classList.contains("selected");
      group.querySelectorAll(".score-btn").forEach((b) => b.classList.remove("selected"));
      if (!isSelected) btn.classList.add("selected");
    });
  });

  document.getElementById("btn-prev").addEventListener("click", () => shiftDate(-1));
  document.getElementById("btn-next").addEventListener("click", () => shiftDate(1));

  function shiftDate(days) {
    const d = new Date(dateInput.value);
    d.setDate(d.getDate() + days);
    dateInput.value = d.toISOString().slice(0, 10);
    fetchAndRestore(dateInput.value);
  }

  dateInput.addEventListener("change", () => fetchAndRestore(dateInput.value));

  document.getElementById("btn-clear").addEventListener("click", async () => {
    if (!confirm("この日の記録をすべてクリアしますか？")) return;
    clearAll();
    noteInput.value = "";
    const date = dateInput.value;
    const payload = [];
    document.querySelectorAll(".score-buttons").forEach((group) => {
      payload.push({ date, symptom: group.dataset.symptom, timepoint: group.dataset.timepoint, score: null });
    });
    await fetch("/api/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date, entries: payload, note: "" }),
    });
    showSaveMsg("クリアしました");
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const date = dateInput.value;
    const entries = collectEntries(date);
    const note = noteInput.value;
    try {
      const res = await fetch("/api/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date, entries, note }),
      });
      if (res.ok) {
        showSaveMsg("保存しました");
      } else {
        alert("保存に失敗しました");
      }
    } catch {
      alert("通信エラーが発生しました");
    }
  });

  function collectEntries(date) {
    const entries = [];
    document.querySelectorAll(".score-buttons").forEach((group) => {
      const symptom = group.dataset.symptom;
      const timepoint = group.dataset.timepoint;
      const selected = group.querySelector(".score-btn.selected");
      const score = selected
        ? selected.dataset.score === "none" ? -1 : parseInt(selected.dataset.score, 10)
        : null;
      entries.push({ date, symptom, timepoint, score });
    });
    return entries;
  }

  function restoreExisting(data) {
    document.querySelectorAll(".score-buttons").forEach((group) => {
      const key = `${group.dataset.symptom}_${group.dataset.timepoint}`;
      if (!(key in data)) return;
      const val = data[key];
      const scoreStr = val === -1 ? "none" : String(val);
      const btn = group.querySelector(`.score-btn[data-score="${scoreStr}"]`);
      if (btn) btn.classList.add("selected");
    });
  }

  function clearAll() {
    document.querySelectorAll(".score-btn").forEach((b) => b.classList.remove("selected"));
  }

  async function fetchAndRestore(date) {
    clearAll();
    noteInput.value = "";
    try {
      const res = await fetch(`/api/records?date=${date}`);
      if (res.ok) {
        const data = await res.json();
        restoreExisting(data.records);
        noteInput.value = data.note || "";
      }
    } catch {}
  }

  function showSaveMsg(text) {
    saveMsg.textContent = text;
    saveMsg.hidden = false;
    setTimeout(() => { saveMsg.hidden = true; }, 2500);
  }
});
