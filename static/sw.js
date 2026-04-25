// Service Worker PWA — TUC TUC

self.addEventListener('install', () => { self.skipWaiting(); });
self.addEventListener('activate', (e) => { e.waitUntil(clients.claim()); });
self.addEventListener('fetch', (e) => { e.respondWith(fetch(e.request)); });

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const url = event.notification.data?.url || '/';
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
            for (const c of list) {
                if (c.url.includes(self.location.origin) && 'focus' in c) {
                    c.navigate(url); return c.focus();
                }
            }
            if (clients.openWindow) return clients.openWindow(url);
        })
    );
});
