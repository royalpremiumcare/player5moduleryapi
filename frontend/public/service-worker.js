// PLANN PWA Service Worker
const CACHE_NAME = 'plann-cache-v21';
const OFFLINE_URL = '/offline.html';

// Önbelleğe alınacak statik kaynaklar
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/offline.html',
  '/manifest.json',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
  '/icons/badge-mono-96x96.png'
];

// API istekleri için cache stratejisi (Network First)
const API_CACHE_NAME = 'plann-api-cache-v2';
const API_ENDPOINTS = [
  '/api/appointments',
  '/api/services',
  '/api/settings',
  '/api/stats/dashboard'
];

// Install Event - Statik dosyaları önbelleğe al
self.addEventListener('install', (event) => {
  console.log('[ServiceWorker] Install');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[ServiceWorker] Caching static assets');
        return cache.addAll(STATIC_ASSETS.filter(url => !url.includes('/api/')));
      })
      .then(() => self.skipWaiting())
      .catch((error) => {
        console.error('[ServiceWorker] Cache addAll failed:', error);
      })
  );
});

// Activate Event - Eski cache'leri temizle
self.addEventListener('activate', (event) => {
  console.log('[ServiceWorker] Activate');
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== CACHE_NAME && cacheName !== API_CACHE_NAME) {
              console.log('[ServiceWorker] Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => self.clients.claim())
  );
});

// Fetch Event - İstekleri yönet
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // POST, PUT, DELETE isteklerini cache'leme - direkt network'e gönder
  if (request.method !== 'GET') {
    event.respondWith(fetch(request));
    return;
  }

  // API istekleri için Network First stratejisi
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Statik kaynaklar için Cache First stratejisi
  if (request.destination === 'image' || 
      request.destination === 'style' || 
      request.destination === 'script' ||
      request.destination === 'font') {
    event.respondWith(cacheFirst(request));
    return;
  }

  // HTML sayfaları için Network First
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Başarılı yanıtı cache'e kaydet
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseClone);
          });
          return response;
        })
        .catch(() => {
          // Offline durumunda cache'den veya offline sayfasını göster
          return caches.match(request)
            .then((cachedResponse) => {
              if (cachedResponse) {
                return cachedResponse;
              }
              return caches.match(OFFLINE_URL);
            });
        })
    );
    return;
  }

  // Diğer istekler için stale-while-revalidate
  event.respondWith(staleWhileRevalidate(request));
});

// Cache First Stratejisi
async function cacheFirst(request) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.error('[ServiceWorker] Fetch failed:', error);
    return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
  }
}

// Network First Stratejisi
async function networkFirst(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(API_CACHE_NAME);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.log('[ServiceWorker] Network failed, trying cache');
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    return new Response(JSON.stringify({ error: 'Offline' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

// Stale While Revalidate Stratejisi
async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_NAME);
  const cachedResponse = await cache.match(request);
  
  const fetchPromise = fetch(request)
    .then((networkResponse) => {
      if (networkResponse.ok) {
        cache.put(request, networkResponse.clone());
      }
      return networkResponse;
    })
    .catch(() => cachedResponse);

  return cachedResponse || fetchPromise;
}

// Push Notification Event
self.addEventListener('push', (event) => {
  console.log('[ServiceWorker] Push received');
  
  let data = { title: 'PLANN', body: 'Yeni bildirim', url: '/' };
  
  if (event.data) {
    try {
      const jsonData = event.data.json();
      data = { ...data, ...jsonData };
    } catch (e) {
      data.body = event.data.text();
    }
  }

  // Backend payload'unda derin bağlantı bilgisi nested `data` objesindedir
  // (ör. { data: { url: '/?randevu=<id>', appointment_id, type } }).
  const payloadData = data.data || {};
  const targetUrl = payloadData.url || data.url || '/';

  const options = {
    body: data.body,
    icon: data.icon || 'https://plannapp.co/icons/icon-192x192.png',
    badge: data.badge || 'https://plannapp.co/icons/badge-mono-96x96.png',
    vibrate: [100, 50, 100],
    data: {
      url: targetUrl,
      appointmentId: payloadData.appointment_id,
      type: payloadData.type,
      timestamp: Date.now()
    },
    requireInteraction: true, // Kullanıcı müdahale edene kadar ekranda kalsın
    actions: [
      { action: 'open', title: 'Görüntüle' },
      { action: 'close', title: 'Kapat' }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification Click Event
self.addEventListener('notificationclick', (event) => {
  console.log('[ServiceWorker] Notification click');
  event.notification.close();

  if (event.action === 'close') {
    return;
  }

  const nd = event.notification.data || {};
  const urlToOpen = nd.url || '/';
  const aptId = nd.appointmentId;

  event.waitUntil((async () => {
    // 1) Randevu id'sini Cache'e yaz. iOS bildirime dokununca kurulu PWA'yı
    //    zaten öne getirir; PWA görünür olunca (visibilitychange) bunu okuyup
    //    detayı açar. Böylece Safari'ye kaçış ve postMessage zamanlama yarışı
    //    ortadan kalkar (iOS PWA için en güvenilir yol).
    if (aptId) {
      try {
        const cache = await caches.open('plann-pending');
        await cache.put(
          '/__pending_appointment',
          new Response(JSON.stringify({ appointmentId: aptId, ts: Date.now() }), {
            headers: { 'Content-Type': 'application/json' },
          })
        );
      } catch (e) { /* cache yoksa yoksay */ }
    }

    // 2) Açık bir uygulama penceresi varsa odakla + postMessage (sıcak durum,
    //    reload olmadan anında açılır). navigate/openWindow İLE Safari'ye
    //    kaçmamak için burada YALNIZCA focus + mesaj kullanıyoruz.
    const clientList = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    const client = clientList.find((c) => 'focus' in c);
    if (client) {
      try { await client.focus(); } catch (e) { /* yoksay */ }
      if (aptId) {
        try { client.postMessage({ type: 'OPEN_APPOINTMENT', appointmentId: aptId }); } catch (e) { /* yoksay */ }
      }
      return;
    }

    // 3) Hiç açık pencere yoksa (uygulama kapalı) yeni pencere aç.
    //    Soğuk başlangıç → ?randevu param'ı VEYA pending cache okunur.
    if (clients.openWindow) {
      await clients.openWindow(urlToOpen);
    }
  })());
});

// Background Sync Event
self.addEventListener('sync', (event) => {
  console.log('[ServiceWorker] Sync event:', event.tag);
  
  if (event.tag === 'sync-appointments') {
    event.waitUntil(syncAppointments());
  }
});

// Randevuları senkronize et
async function syncAppointments() {
  try {
    // IndexedDB'den bekleyen randevuları al ve gönder
    console.log('[ServiceWorker] Syncing appointments...');
    // Bu fonksiyon gerektiğinde doldurulabilir
  } catch (error) {
    console.error('[ServiceWorker] Sync failed:', error);
  }
}

// Periodic Background Sync
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'refresh-data') {
    event.waitUntil(refreshData());
  }
});

async function refreshData() {
  console.log('[ServiceWorker] Periodic sync - refreshing data');
  // Arka planda veri güncelleme
}

console.log('[ServiceWorker] Service Worker loaded');
