// Bump the version whenever index.html or the vendored assets change.
const CACHE = 'gorillastats-shell-v1';
const SHELL = [
  '/',
  '/manifest.webmanifest',
  '/logo.png',
  '/static/vendor/chart.umd.min.js',
  '/static/vendor/fonts.css',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then(async (cache) => {
      await cache.addAll(SHELL);
      const css = await (await cache.match('/static/vendor/fonts.css')).text();
      await cache.addAll([...css.matchAll(/url\('([^']+)'\)/g)].map((match) => match[1]));
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  // API calls and uploads always go to the network so data is never stale or cached.
  if (request.method !== 'GET' || url.origin !== location.origin
      || url.pathname.startsWith('/api/') || url.pathname.startsWith('/static/media/')) {
    return;
  }
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put('/', copy));
        return response;
      }).catch(() => caches.match('/'))
    );
    return;
  }
  event.respondWith(caches.match(request).then((cached) => cached || fetch(request)));
});
