import http from 'k6/http';
import { sleep, check } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// ─────────────────────────────────────────────────────────────────────────────
// PLANN k6 — 3 Profilli Yük Testi
//   PROFILE=cold  → cache boş (orchestrator flush eder). Cache-miss + Mongo.
//   PROFILE=warm  → cache dolu (orchestrator prewarm eder). Gerçek UX'e en yakın.
//   PROFILE=large → İZOLE sentetik org (10k müşteri / 100k randevu). Ölçek testi.
//
// Env: PROFILE, TOKEN, BASE_URL (varsayılan http://127.0.0.1:8002/api)
// ─────────────────────────────────────────────────────────────────────────────

const PROFILE = __ENV.PROFILE || 'warm';
const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8002/api';
const TOKEN = __ENV.TOKEN || '';

const errorRate = new Rate('errors');
const trends = {
  dashboard: new Trend('dashboard_duration'),
  appointments: new Trend('appointments_duration'),
  appointments_paginated: new Trend('appointments_paginated_duration'),
  services: new Trend('services_duration'),
  customers: new Trend('customers_duration'),
  customers_paginated: new Trend('customers_paginated_duration'),
  customers_search: new Trend('customers_search_duration'),
};

// Ölçek-hassas çekirdek set (large profilinde bunlar anlamlı)
const CORE = [
  { name: 'Dashboard Stats',              url: '/stats/dashboard',                 trend: 'dashboard' },
  { name: 'Appointments (legacy flat)',   url: '/appointments',                    trend: 'appointments' },
  { name: 'Appointments (paginated 30)',  url: '/appointments?limit=30',           trend: 'appointments_paginated' },
  { name: 'Services',                     url: '/services',                        trend: 'services' },
  { name: 'Customers (legacy flat)',      url: '/customers',                       trend: 'customers' },
  { name: 'Customers (paginated 30)',     url: '/customers?limit=30',              trend: 'customers_paginated' },
  { name: 'Customers (search)',           url: '/customers?limit=30&search=fatih', trend: 'customers_search' },
];

// Gerçek org profillerinde (cold/warm) ek panel endpoint'leri de yüke dahil
const EXTRA = [
  { name: 'Settings',        url: '/settings',        trend: null },
  { name: 'Users',           url: '/users',           trend: null },
  { name: 'Finance Summary', url: '/finance/summary', trend: null },
  { name: 'Expenses',        url: '/expenses',        trend: null },
  { name: 'Payroll',         url: '/finance/payroll', trend: null },
  { name: 'Current Plan',    url: '/plan/current',    trend: null },
];

const endpoints = PROFILE === 'large' ? CORE : CORE.concat(EXTRA);

// Large profili TEK org'a vurur; tek işletmede 1000 eşzamanlı kullanıcı
// gerçekçi değil (ve legacy ağır payload'lar 17 worker'ı doyurup tüm API'yi
// erittiğini T-large-1000 koşusunda gördük). Bu yüzden large'da gerçekçi bir
// peak (100 VU) kullanıyoruz → per-endpoint ölçek latency'si temiz çıkar.
const STAGES_FULL = [
  { duration: '15s', target: 100 },
  { duration: '15s', target: 300 },
  { duration: '30s', target: 500 },
  { duration: '30s', target: 750 },
  { duration: '30s', target: 1000 },
  { duration: '20s', target: 0 },
];
const STAGES_SCALE = [
  { duration: '15s', target: 25 },
  { duration: '30s', target: 50 },
  { duration: '45s', target: 100 },
  { duration: '20s', target: 0 },
];

export const options = {
  stages: PROFILE === 'large' ? STAGES_SCALE : STAGES_FULL,
  thresholds: {
    http_req_duration: ['p(95)<2000'],
    errors: ['rate<0.05'],
  },
  tags: { profile: PROFILE },
};

const params = {
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    'Content-Type': 'application/json',
  },
};

export default function () {
  const ep = endpoints[Math.floor(Math.random() * endpoints.length)];
  const res = http.get(`${BASE_URL}${ep.url}`, params);
  const ok = check(res, { [`${ep.name} OK (200)`]: (r) => r.status === 200 });
  errorRate.add(!ok);
  if (ep.trend && trends[ep.trend]) trends[ep.trend].add(res.timings.duration);
  sleep(0.1);
}
