/* ============================================================
   pwa.js — Service Worker 登録 + インストールプロンプト管理
   全ページで読み込まれる（_pwa_head.html 経由）
   ============================================================ */

(function () {
  'use strict';

  // ---- 1. Service Worker 登録 ----
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then(reg => {
          // 新しいバージョンが待機中なら次回起動時に適用
          reg.addEventListener('updatefound', () => {
            const nw = reg.installing;
            if (!nw) return;
            nw.addEventListener('statechange', () => {
              if (nw.state === 'installed' && navigator.serviceWorker.controller) {
                console.log('[SW] 新バージョンが利用可能。次回起動時に適用されます。');
              }
            });
          });
        })
        .catch(err => console.warn('[SW] 登録失敗:', err));
    });
  }

  // ---- 2. beforeinstallprompt キャプチャ ----
  let _deferredPrompt = null;

  window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault();
    _deferredPrompt = e;
    // id="pwa-install-btn" がページ上にあれば表示する
    _showInstallButtons();
  });

  // インストール完了後は非表示
  window.addEventListener('appinstalled', () => {
    _deferredPrompt = null;
    _hideInstallButtons();
    console.log('[PWA] インストール完了');
  });

  function _showInstallButtons() {
    document.querySelectorAll('[data-pwa-install]').forEach(el => {
      el.style.display = '';
    });
  }

  function _hideInstallButtons() {
    document.querySelectorAll('[data-pwa-install]').forEach(el => {
      el.style.display = 'none';
    });
  }

  // DOM 構築後にも一度チェック（DOMContentLoaded 後に pwa.js が走った場合）
  document.addEventListener('DOMContentLoaded', () => {
    if (_deferredPrompt) _showInstallButtons();

    // data-pwa-install 属性を持つ全要素にクリックハンドラを設定
    document.querySelectorAll('[data-pwa-install]').forEach(el => {
      el.addEventListener('click', triggerInstall);
    });
  });

  // ---- 3. 公開 API ----
  /**
   * PWA インストールダイアログを表示する。
   * ボタンの onclick="triggerInstall()" で呼べる。
   */
  window.triggerInstall = async function () {
    if (!_deferredPrompt) return;
    _deferredPrompt.prompt();
    const { outcome } = await _deferredPrompt.userChoice;
    console.log('[PWA] ユーザーの選択:', outcome);
    _deferredPrompt = null;
    _hideInstallButtons();
  };

  /** インストール可能かどうかを返す */
  window.isPWAInstallable = function () {
    return _deferredPrompt !== null;
  };
})();
