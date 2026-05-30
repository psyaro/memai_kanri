/* ============================================================
   Service Worker — SymptoPort
   戦略:
     - 静的アセット (CSS/JS/アイコン): Cache First
     - ページ (HTML): Network First + フォールバック
     - API (/api/*): Network Only（オフライン時はエラー通知）
   ============================================================ */

const CACHE_VERSION = 'v0.6.4';
const STATIC_CACHE  = `SymptoPort-static-${CACHE_VERSION}`;
const PAGE_CACHE    = `SymptoPort-pages-${CACHE_VERSION}`;

// インストール時にプリキャッシュするアセット
const PRECACHE_ASSETS = [
  '/static/style.css',
  '/static/app.js',
  '/static/settings.js',
  '/static/icons/icon.svg',
  '/static/manifest.json',
];

// オフライン時に表示するフォールバックページ
const OFFLINE_URL = '/login';

// ---- Install ------------------------------------------------
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => {
      return cache.addAll(PRECACHE_ASSETS).catch(err => {
        console.warn('[SW] プリキャッシュ失敗（一部ファイルが存在しない可能性）:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

// ---- Activate -----------------------------------------------
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k !== STATIC_CACHE && k !== PAGE_CACHE)
          .map(k => {
            console.log('[SW] 古いキャッシュを削除:', k);
            return caches.delete(k);
          })
      )
    ).then(() => self.clients.claim())
  );
});

// ---- Fetch --------------------------------------------------
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // 別オリジン（Turnstile 等）はスルー
  if (url.origin !== location.origin) return;

  // API リクエスト: Network Only
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request).catch(() =>
        new Response(JSON.stringify({ error: 'オフラインです。ネットワークを確認してください。' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        })
      )
    );
    return;
  }

  // 静的アセット: Cache First
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;
        return fetch(request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(STATIC_CACHE).then(c => c.put(request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // HTML ページ: Network First（失敗時はキャッシュ → フォールバック）
  if (request.mode === 'navigate' || request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(PAGE_CACHE).then(c => c.put(request, clone));
          }
          return response;
        })
        .catch(async () => {
          const cached = await caches.match(request);
          if (cached) return cached;
          // キャッシュもなければログインページへ
          return caches.match(OFFLINE_URL) ||
            new Response('<h1>オフラインです</h1><p>ネットワークに接続してから再試行してください。</p>', {
              headers: { 'Content-Type': 'text/html; charset=utf-8' },
            });
        })
    );
    return;
  }
});

// ---- Background Sync (将来用) --------------------------------
self.addEventListener('sync', event => {
  if (event.tag === 'sync-records') {
    // TODO: オフライン中に保留した記録を再送信する処理
    console.log('[SW] Background Sync: sync-records');
  }
});
