const CACHE_NAME = "mfe-study-public-v1";
const PUBLIC_ASSETS = [
  "/static/app.css",
  "/static/app.js",
  "/static/icon-192.png",
  "/static/icon-512.png",
  "/static/offline.html",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(PUBLIC_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/static/") && url.pathname !== "/static/offline.html") {
    event.respondWith(caches.match(request).then((cached) => cached || fetch(request)));
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match("/static/offline.html")));
  }
});
