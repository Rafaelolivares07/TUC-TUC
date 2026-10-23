// Service Worker PWA — TUC TUC (con soporte nativo Web Push VAPID)

self.addEventListener('install', () => { self.skipWaiting(); });
self.addEventListener('activate', (e) => { e.waitUntil(clients.claim()); });
self.addEventListener('fetch', (e) => { e.respondWith(fetch(e.request)); });

// Evento PUSH nativo (se dispara aun con la app o el navegador cerrados)
self.addEventListener('push', (event) => {
    let payload = {};
    if (event.data) {
        try {
            payload = event.data.json();
        } catch (e) {
            payload = { title: 'TUC TUC Mensajería', body: event.data.text() };
        }
    }
    const title = payload.title || 'Nuevo mensaje en TUC TUC';
    const body = payload.body || 'Tienes un nuevo mensaje.';
    const icon = payload.icon || '/static/icons/icon-192.png';
    const badge = payload.badge || '/static/icons/icon-192.png';
    const token = payload.token || '';
    const targetUrl = payload.url || (token ? ('/chat2?open_token=' + encodeURIComponent(token)) : '/chat2');

    const options = {
        body: body,
        icon: icon,
        badge: badge,
        image: payload.image || undefined,
        tag: payload.tag || ('chat-' + (token || Date.now())),
        renotify: true,
        vibrate: [300, 120, 300, 120, 450],
        requireInteraction: true,
        data: {
            url: targetUrl,
            token: token,
            timestamp: Date.now()
        },
        actions: [
            { action: 'abrir', title: 'Abrir Chat' }
        ]
    };

    event.waitUntil(
        Promise.all([
            self.registration.showNotification(title, options),
            clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
                for (const client of clientList) {
                    try {
                        client.postMessage({
                            type: 'tuctuc_push_recibido',
                            title: title,
                            body: body,
                            url: targetUrl,
                            token: token
                        });
                    } catch(e) {}
                }
            })
        ])
    );
});

// Clic en la notificación (abre o enfoca la conversación en primer plano)
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const data = event.notification.data || {};
    const targetUrl = data.url || '/chat2';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
            for (const client of clientList) {
                if (client.url && client.url.includes(self.location.origin) && 'focus' in client) {
                    try {
                        client.postMessage({
                            type: 'tuctuc_push_click',
                            url: targetUrl,
                            token: data.token
                        });
                    } catch (e) {}
                    if ('navigate' in client && client.url.indexOf(targetUrl) === -1) {
                        client.navigate(targetUrl);
                    }
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});
