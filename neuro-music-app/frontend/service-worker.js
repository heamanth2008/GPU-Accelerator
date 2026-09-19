self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open('neuro-music-cache').then((cache) => {
      return cache.addAll([
        '/',
        '/glass_home.html',
        '/glass_player.html',
        '/style.css',
        '/app.js',
        '/manifest.webmanifest',
        // add any icons you have
      ]);
    })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
