const CACHE_NAME = 'stafftrack-v4';
const STATIC_ASSETS = [
  '/',
  '/manifest.json',
  '/Statics/css/style.css',
  '/Statics/js/app.js',
  '/Statics/icons/icon-192.png',
  '/Statics/icons/icon-512.png',
  '/Statics/icons/icon.svg'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('SW cache.addAll non-critical warning:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  // Network first with fallback to cache for offline static assets
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
