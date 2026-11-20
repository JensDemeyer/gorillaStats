// Bump the version whenever the vendored assets, icons or stage images change.
// App code (index.html, /static/js, /static/css) is network-first, so a git pull is enough.
const CACHE = 'gorillastats-shell-v2';
const SHELL = [
  '/',
  '/manifest.webmanifest',
  '/logo.png',
  '/static/vendor/chart.umd.min.js',
  '/static/vendor/fonts.css',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/css/app.css',
  '/static/js/select.js',
  '/static/js/motivation.js',
  '/static/js/coach.js',
  '/static/js/journey.js',
  '/static/js/body.js',
  '/static/js/dashboard.js',
  '/static/js/cardio.js',
  '/static/stages/baby.webp',
  '/static/stages/puber.webp',
  '/static/stages/alfa.webp',
  '/static/stages/ultra-alfa.webp',
];
const NETWORK_FIRST = ['/static/js/', '/static/css/'];

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
  if (NETWORK_FIRST.some((prefix) => url.pathname.startsWith(prefix))) {
    event.respondWith(
      fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(request, copy));
        return response;
      }).catch(() => caches.match(request))
    );
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
