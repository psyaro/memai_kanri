document.addEventListener("DOMContentLoaded", () => {
  const dateInput = document.getElementById("date-input");
  const form = document.getElementById("record-form");
  const saveMsg = document.getElementById("save-msg");
  const noteInput = document.getElementById("note-input");

  // WBGT関連のDOM
  const taInput = document.getElementById("wbgt-ta");
  const rhInput = document.getElementById("wbgt-rh");
  const srInput = document.getElementById("wbgt-sr");
  const wsInput = document.getElementById("wbgt-ws");
  const wbgtVal = document.getElementById("wbgt-val");
  const wbgtLevelText = document.getElementById("wbgt-level");
  const fetchWbgtBtn = document.getElementById("btn-fetch-wbgt");
  const clearCacheBtn = document.getElementById("btn-clear-weather-cache");
  const fetchStatus = document.getElementById("wbgt-fetch-status");
  const statusBadge = document.getElementById("wbgt-status-badge");

  // 一括取得用のDOM
  const batchFetch30dBtn = document.getElementById("btn-batch-fetch-30d");
  const batchClearFetch30dBtn = document.getElementById("btn-batch-clear-fetch-30d");

  // 予報か実績かフラグ (1: 予報, 0: 実測)
  let currentIsForecast = 1;

  restoreExisting(EXISTING);
  restoreWbgt(EXISTING_WBGT);

  // 服薬チェックのトグル
  document.querySelectorAll(".med-toggle-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const isTaken = btn.classList.contains("taken");
      if (isTaken) {
        btn.classList.remove("taken");
        btn.textContent = "未服用";
      } else {
        btn.classList.add("taken");
        btn.textContent = "💊 服用済み";
      }
      requestAutoSave(500); // 500msのデバウンスで自動保存
    });
  });

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

  // WBGT入力欄の変更検知
  [taInput, rhInput, srInput, wsInput].forEach((input) => {
    input.addEventListener("input", () => {
      currentIsForecast = determineForecastStatus();
      calculateWBGT();
      requestAutoSave(1000); // 1000msのデバウンスで保存
    });
  });

  // 東京の14時気象を取得ボタン
  fetchWbgtBtn.addEventListener("click", async () => {
    fetchStatus.textContent = "⚡ 取得中...";
    fetchStatus.hidden = false;
    fetchStatus.className = "wbgt-status-msg status-fetching";
    fetchWbgtBtn.disabled = true;
    clearCacheBtn.disabled = true;

    const date = dateInput.value;
    try {
      const res = await fetch(`/api/tokyo_weather?date=${date}`);
      if (res.ok) {
        const data = await res.json();
        taInput.value = data.ta !== undefined ? data.ta : "";
        rhInput.value = data.rh !== undefined ? data.rh : "";
        srInput.value = data.sr !== undefined ? data.sr : "";
        wsInput.value = data.ws !== undefined ? data.ws : "";
        currentIsForecast = data.is_forecast !== undefined ? data.is_forecast : 1;
        
        calculateWBGT();

        fetchStatus.textContent = data.cached ? "✓ キャッシュから取得しました" : "✓ 最新情報を取得しました";
        fetchStatus.className = "wbgt-status-msg status-success";

        requestAutoSave(500); // 自動保存をスケジュール
      } else {
        fetchStatus.textContent = "✗ 取得に失敗しました";
        fetchStatus.className = "wbgt-status-msg status-error";
      }
    } catch {
      fetchStatus.textContent = "✗ 通信エラーが発生しました";
      fetchStatus.className = "wbgt-status-msg status-error";
    } finally {
      fetchWbgtBtn.disabled = false;
      clearCacheBtn.disabled = false;
      setTimeout(() => {
        fetchStatus.hidden = true;
      }, 3000);
    }
  });

  // キャッシュを強制クリアして最新データを再取得するボタン
  clearCacheBtn.addEventListener("click", async () => {
    fetchStatus.textContent = "🔄 キャッシュを消去中...";
    fetchStatus.hidden = false;
    fetchStatus.className = "wbgt-status-msg status-fetching";
    fetchWbgtBtn.disabled = true;
    clearCacheBtn.disabled = true;

    const date = dateInput.value;
    try {
      const res = await fetch(`/api/tokyo_weather?date=${date}&force=1`);
      if (res.ok) {
        const data = await res.json();
        taInput.value = data.ta !== undefined ? data.ta : "";
        rhInput.value = data.rh !== undefined ? data.rh : "";
        srInput.value = data.sr !== undefined ? data.sr : "";
        wsInput.value = data.ws !== undefined ? data.ws : "";
        currentIsForecast = data.is_forecast !== undefined ? data.is_forecast : 1;
        
        calculateWBGT();

        fetchStatus.textContent = "✓ キャッシュを破棄し、最新情報を再取得しました";
        fetchStatus.className = "wbgt-status-msg status-success";

        requestAutoSave(500); // 自動保存をスケジュール
      } else {
        fetchStatus.textContent = "✗ 更新に失敗しました";
        fetchStatus.className = "wbgt-status-msg status-error";
      }
    } catch {
      fetchStatus.textContent = "✗ 通信エラーが発生しました";
      fetchStatus.className = "wbgt-status-msg status-error";
    } finally {
      fetchWbgtBtn.disabled = false;
      clearCacheBtn.disabled = false;
      setTimeout(() => {
        fetchStatus.hidden = true;
      }, 3000);
    }
  });

  // 直近30日分の一括同期処理
  if (batchFetch30dBtn && batchClearFetch30dBtn) {
    async function runBatch30d(force) {
      showSaveMsg("30日分の一括同期中...", true);
      batchFetch30dBtn.disabled = true;
      batchClearFetch30dBtn.disabled = true;
      fetchWbgtBtn.disabled = true;
      clearCacheBtn.disabled = true;

      // 今日と30日前の日付を計算 (日本時間基準)
      const todayObj = new Date();
      const jstOffset = 9 * 60;
      const localTime = new Date(todayObj.getTime() + (todayObj.getTimezoneOffset() + jstOffset) * 60000);
      const toDate = localTime.toISOString().slice(0, 10);
      
      const fromTime = new Date(localTime.getTime() - 29 * 24 * 60 * 60 * 1000);
      const fromDate = fromTime.toISOString().slice(0, 10);

      try {
        const res = await fetch("/api/tokyo_weather/batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ from_date: fromDate, to_date: toDate, force: force })
        });
        
        if (res.ok) {
          const data = await res.json();
          showSaveMsg(`直近${data.count}日分のデータを同期しました！`);
          
          // 現在表示中の日のデータを再読み込みしてUIに反映
          setTimeout(() => {
            fetchAndRestore(dateInput.value);
          }, 1000);
        } else {
          showSaveMsg("同期に失敗しました", false, true);
        }
      } catch {
        showSaveMsg("通信エラーが発生しました", false, true);
      } finally {
        batchFetch30dBtn.disabled = false;
        batchClearFetch30dBtn.disabled = false;
        fetchWbgtBtn.disabled = false;
        clearCacheBtn.disabled = false;
      }
    }

    batchFetch30dBtn.addEventListener("click", () => runBatch30d(0));
    batchClearFetch30dBtn.addEventListener("click", () => {
      if (confirm("直近30日間の気象キャッシュをすべて破棄し、外部APIから最新の情報を一括再取得します。よろしいですか？")) {
        runBatch30d(1);
      }
    });
  }

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
    clearWbgtForm();
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
    const wbgt_data = collectWbgtData();

    try {
      const res = await fetch("/api/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date, entries, note, wbgt_data }),
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

    // 服薬記録の収集
    document.querySelectorAll(".med-toggle-btn").forEach((btn) => {
      const symptom = "__medication__";
      const timepoint = btn.dataset.timepoint;
      const score = btn.classList.contains("taken") ? 1 : null;
      entries.push({ date, symptom, timepoint, score });
    });

    return entries;
  }

  function collectWbgtData() {
    const ta = taInput.value.trim();
    const rh = rhInput.value.trim();
    const sr = srInput.value.trim();
    const ws = wsInput.value.trim();

    if (ta === "" && rh === "" && sr === "" && ws === "") {
      return null;
    }

    const wbgt = wbgtVal.textContent === "-" ? null : parseFloat(wbgtVal.textContent);

    return {
      ta: ta !== "" ? parseFloat(ta) : null,
      rh: rh !== "" ? parseFloat(rh) : null,
      sr: sr !== "" ? parseFloat(sr) : null,
      ws: ws !== "" ? parseFloat(ws) : null,
      wbgt: wbgt,
      is_forecast: currentIsForecast
    };
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

    // 服薬記録の復元
    document.querySelectorAll(".med-toggle-btn").forEach((btn) => {
      btn.classList.remove("taken");
      btn.textContent = "未服用";
      const key = `__medication___${btn.dataset.timepoint}`;
      if (key in data && data[key] === 1) {
        btn.classList.add("taken");
        btn.textContent = "💊 服用済み";
      }
    });
  }

  function restoreWbgt(data) {
    if (!data || Object.keys(data).length === 0) {
      clearWbgtForm();
      return;
    }
    taInput.value = data.ta !== null && data.ta !== undefined ? data.ta : "";
    rhInput.value = data.rh !== null && data.rh !== undefined ? data.rh : "";
    srInput.value = data.sr !== null && data.sr !== undefined ? data.sr : "";
    wsInput.value = data.ws !== null && data.ws !== undefined ? data.ws : "";
    currentIsForecast = (data.is_forecast !== undefined && data.is_forecast !== null) ? data.is_forecast : 1;
    calculateWBGT();
  }

  function determineForecastStatus() {
    const selectedDate = dateInput.value;
    const today = new Date();
    // 日本時間(JST = UTC+9)に変換
    const jstOffset = 9 * 60;
    const localTime = new Date(today.getTime() + (today.getTimezoneOffset() + jstOffset) * 60 * 1000);
    const todayStr = localTime.toISOString().slice(0, 10);
    
    if (selectedDate < todayStr) {
      return 0; // 過去は確定実績値
    } else if (selectedDate > todayStr) {
      return 1; // 未来は予報値
    } else {
      // 今日：14時以降は実測、それ以外は予報
      return localTime.getHours() >= 14 ? 0 : 1;
    }
  }

  function calculateWBGT() {
    const ta = parseFloat(taInput.value);
    const rh = parseFloat(rhInput.value);
    const sr = parseFloat(srInput.value);
    const ws = parseFloat(wsInput.value);

    if (isNaN(ta) || isNaN(rh) || isNaN(sr) || isNaN(ws)) {
      wbgtVal.textContent = "-";
      wbgtLevelText.textContent = "";
      wbgtLevelText.className = "wbgt-level-text";
      updateStatusBadge();
      return null;
    }

    // WBGT＝0.735×Ta＋0.0374×RH＋0.00292×Ta×RH＋7.619×SR－4.557×SR^2－0.0572×WS－4.064
    const wbgt = 0.735 * ta 
               + 0.0374 * rh 
               + 0.00292 * ta * rh 
               + 7.619 * sr 
               - 4.557 * (sr * sr) 
               - 0.0572 * ws 
               - 4.064;
    const result = Math.round(wbgt * 10) / 10;
    
    if (result < 0) {
      wbgtVal.textContent = "-";
      wbgtLevelText.textContent = "";
      wbgtLevelText.className = "wbgt-level-text";
      updateStatusBadge();
      return null;
    }
    
    wbgtVal.textContent = result.toFixed(1);

    updateWbgtLevel(result);
    updateStatusBadge();
    return result;
  }

  function updateStatusBadge() {
    if (wbgtVal.textContent === "-") {
      statusBadge.textContent = "";
      statusBadge.style.display = "none";
      return;
    }
    statusBadge.style.display = "inline-block";
    if (currentIsForecast === 1) {
      statusBadge.textContent = "予報";
      statusBadge.className = "wbgt-status-badge status-forecast-badge";
    } else {
      statusBadge.textContent = "実測";
      statusBadge.className = "wbgt-status-badge status-actual-badge";
    }
  }

  function updateWbgtLevel(wbgt) {
    let level = "";
    let className = "wbgt-level-text ";

    if (wbgt < 21) {
      level = "ほぼ安全";
      className += "level-safe";
    } else if (wbgt < 25) {
      level = "注意";
      className += "level-caution";
    } else if (wbgt < 28) {
      level = "警戒";
      className += "level-warning";
    } else if (wbgt < 31) {
      level = "厳重警戒";
      className += "level-severe";
    } else {
      level = "危険";
      className += "level-danger";
    }

    wbgtLevelText.textContent = `レベル: ${level}`;
    wbgtLevelText.className = className;
  }

  function clearAll() {
    document.querySelectorAll(".score-btn").forEach((b) => b.classList.remove("selected"));
    document.querySelectorAll(".med-toggle-btn").forEach((btn) => {
      btn.classList.remove("taken");
      btn.textContent = "未服用";
    });
  }

  function clearWbgtForm() {
    taInput.value = "";
    rhInput.value = "";
    srInput.value = "";
    wsInput.value = "";
    wbgtVal.textContent = "-";
    wbgtLevelText.textContent = "";
    wbgtLevelText.className = "wbgt-level-text";
    currentIsForecast = 1;
    updateStatusBadge();
  }

  async function fetchAndRestore(date) {
    clearAll();
    noteInput.value = "";
    clearWbgtForm();
    try {
      const res = await fetch(`/api/records?date=${date}`);
      if (res.ok) {
        const data = await res.json();
        restoreExisting(data.records);
        noteInput.value = data.note || "";
        restoreWbgt(data.wbgt);
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
