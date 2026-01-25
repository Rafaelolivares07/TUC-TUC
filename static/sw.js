// Service Worker para PWA con Push Notifications (Firebase Cloud Messaging)

// Importar Firebase SDK para service worker
importScripts('https://www.gstatic.com/firebasejs/9.22.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.22.0/firebase-messaging-compat.js');

// Inicializar Firebase en el service worker
firebase.initializeApp({
    apiKey: "AIzaSyAWkFO0cnmsbM4-faqoVS-G7ecXjvOJN3A",
    authDomain: "tuc-tuc-4f1e5.firebaseapp.com",
    projectId: "tuc-tuc-4f1e5",
    storageBucket: "tuc-tuc-4f1e5.firebasestorage.app",
    messagingSenderId: "448460808766",
    appId: "1:448460808766:web:831e7c76a99ed304e1a76f"
});

const messaging = firebase.messaging();

// Manejar mensajes en segundo plano
messaging.onBackgroundMessage((payload) => {
    console.log('Mensaje en segundo plano:', payload);

    const notificationTitle = payload.notification?.title || payload.data?.titulo || 'TUC TUC';
    const notificationOptions = {
        body: payload.notification?.body || payload.data?.mensaje || 'Tienes una nueva notificacion',
        icon: '/static/TUCTUC%20192X192.png',
        badge: '/static/TUCTUC%20192X192.png',
        vibrate: [200, 100, 200],
        data: {
            url: payload.data?.url || '/'
        }
    };

    return self.registration.showNotification(notificationTitle, notificationOptions);
});

// PWA install/activate events
self.addEventListener('install', (e) => {
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(clients.claim());
});

self.addEventListener('fetch', (e) => {
    e.respondWith(fetch(e.request));
});

// Manejar clic en notificacion
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    const urlToOpen = event.notification.data?.url || '/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
            for (const client of clientList) {
                if (client.url.includes(self.location.origin) && 'focus' in client) {
                    client.navigate(urlToOpen);
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(urlToOpen);
            }
        })
    );
});
