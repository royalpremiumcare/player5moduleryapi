import http from 'k6/http';
import { sleep, check, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const dashboardDuration = new Trend('dashboard_duration');
const appointmentsDuration = new Trend('appointments_duration');
const servicesDuration = new Trend('services_duration');
const customersDuration = new Trend('customers_duration');

export let options = {
  stages: [
    { duration: '15s', target: 100 },   // Isınma
    { duration: '15s', target: 300 },   // Rampa
    { duration: '30s', target: 500 },   // Ağır yük
    { duration: '30s', target: 750 },   // Çok ağır yük
    { duration: '30s', target: 1000 },  // EKSTREM — 1000 VU
    { duration: '20s', target: 0 },     // Soğuma
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'],  // p95 < 2 saniye
    errors: ['rate<0.05'],              // Hata oranı < %5
  },
};

const BASE_URL = 'http://127.0.0.1:8002/api';
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJyb3lhbHByZW1pdW1jYXJlQGdtYWlsLmNvbSIsIm9yZ19pZCI6ImJkMjE1ZGIwLWNkN2QtNDZiYi1hMDkxLWEyMDVhNjI0YjQ1YiIsInJvbGUiOiJhZG1pbiIsIm9uYm9hcmRpbmdfY29tcGxldGVkIjp0cnVlLCJmdWxsX25hbWUiOiJGYXRpaCBcdTAxNWVlbnlcdTAwZmN6IiwiY2FuX3ZpZXdfYWxsX2FwcG9pbnRtZW50cyI6ZmFsc2UsImV4cCI6MTc3MjU5MDcyN30.I2y0byRmMkFnI6dO7y6A9G1962kCynlo-MbkGswenZA';

const params = {
  headers: {
    'Authorization': `Bearer ${TOKEN}`,
    'Content-Type': 'application/json',
  },
};

// Tüm GET endpoint'leri — iş mantığı hatası OLMAZ
const endpoints = [
  { name: 'Dashboard Stats',  url: '/stats/dashboard',           trend: 'dashboard' },
  { name: 'Appointments',     url: '/appointments',              trend: 'appointments' },
  { name: 'Services',         url: '/services',                  trend: 'services' },
  { name: 'Customers',        url: '/customers',                 trend: 'customers' },
  { name: 'Settings',         url: '/settings',                  trend: null },
  { name: 'Users',            url: '/users',                     trend: null },
  { name: 'Finance Summary',  url: '/finance/summary',           trend: null },
  { name: 'Expenses',         url: '/expenses',                  trend: null },
  { name: 'Payroll',          url: '/finance/payroll',           trend: null },
  { name: 'Current Plan',     url: '/plan/current',             trend: null },
];

const trendMap = {
  dashboard: dashboardDuration,
  appointments: appointmentsDuration,
  services: servicesDuration,
  customers: customersDuration,
};

export default function () {
  // Her VU rastgele bir endpoint seçer — gerçek kullanımı simüle eder
  const ep = endpoints[Math.floor(Math.random() * endpoints.length)];

  const res = http.get(`${BASE_URL}${ep.url}`, params);

  const success = check(res, {
    [`${ep.name} OK (200)`]: (r) => r.status === 200,
  });

  errorRate.add(!success);

  if (ep.trend && trendMap[ep.trend]) {
    trendMap[ep.trend].add(res.timings.duration);
  }

  // Minimal bekleme — gerçek yükü simüle et
  sleep(0.1);
}