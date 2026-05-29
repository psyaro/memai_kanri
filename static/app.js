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

      requestAutoSave(500); // ボタン連打防止（500msのデバウンス）
    });
  });

  // 備考：デバウンスで保存
  noteInput.addEventListener("input", () => {
    requestAutoSave(1000); // テキスト入力は1000msのデバウンス
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
    await executeSave();
    showSaveMsg("クリアしました");
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault(); // エンターキーなどでの意図しない送信を防ぐ
  });

  let saveTimeout = null;
  let isSaving = false;

  function requestAutoSave(delay) {
    showSaveMsg("入力中...", true);
    if (saveTimeout) clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => {
      executeSave();
    }, delay);
  }

  async function executeSave() {
    if (isSaving) {
      // すでに保存中の場合は、取りこぼしを防ぐために再スケジュールする
      requestAutoSave(500);
      return;
    }

    isSaving = true;
    showSaveMsg("保存中...", true);
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
        showSaveMsg("保存に失敗しました", false, true);
      }
    } catch {
      showSaveMsg("通信エラーが発生しました", false, true);
    } finally {
      isSaving = false;
    }
  }

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

  let msgTimeout = null;
  function showSaveMsg(text, isPending = false, isError = false) {
    saveMsg.textContent = text;
    saveMsg.hidden = false;

    if (isError) {
      saveMsg.style.backgroundColor = "#fdecea";
      saveMsg.style.color = "#c0392b";
    } else if (isPending) {
      saveMsg.style.backgroundColor = "#fff3cd";
      saveMsg.style.color = "#856404";
    } else {
      saveMsg.style.backgroundColor = "#eafaf1";
      saveMsg.style.color = "#1e8449";
    }

    if (msgTimeout) clearTimeout(msgTimeout);

    if (!isPending && !isError) {
      msgTimeout = setTimeout(() => {
        saveMsg.hidden = true;
      }, 2500);
    }
  }
});

// Service Worker 登録・PWA インストールは pwa.js で一元管理
