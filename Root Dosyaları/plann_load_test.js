import http from 'k6/http';
import { sleep, check, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const dashboardDuration = new Trend('dashboard_duration');
const appointmentsDuration = new Trend('appointments_duration');
const servicesDuration = new Trend('services_duration');
const customersDuration = new Trend('customers_duration');
const customersPagedDuration = new Trend('customers_paginated_duration');
const customersSearchDuration = new Trend('customers_search_duration');

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
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJyb3lhbHByZW1pdW1jYXJlQGdtYWlsLmNvbSIsInVzZXJfaWQiOiJlNzg2Yzk1Yi1hODIwLTRjYmUtYjgwNS1hOTZmMDdkMGY2ZDgiLCJvcmdfaWQiOiJiZDIxNWRiMC1jZDdkLTQ2YmItYTA5MS1hMjA1YTYyNGI0NWIiLCJyb2xlIjoiYWRtaW4iLCJjb21wYW55X25hbWUiOiJSb3lhbCBQcmVtaXVtIENhcmUiLCJmdWxsX25hbWUiOiJGYXRpaCBcdTAxNWVlbnlcdTAwZmN6IiwiY2FuX3ZpZXdfYWxsX2FwcG9pbnRtZW50cyI6ZmFsc2UsIm9uYm9hcmRpbmdfY29tcGxldGVkIjp0cnVlLCJleHAiOjE3ODYwNTIwOTF9.E-FZ4VkEGRBIf0i5emBi3AxPPLk9d_Kh3KzfZHap9sM';

const params = {
  headers: {
    'Authorization': `Bearer ${TOKEN}`,
    'Content-Type': 'application/json',
  },
};

// Tüm GET endpoint'leri — iş mantığı hatası OLMAZ
const endpoints = [
  { name: 'Dashboard Stats',              url: '/stats/dashboard',           trend: 'dashboard' },
  { name: 'Appointments',                 url: '/appointments',              trend: 'appointments' },
  { name: 'Services',                     url: '/services',                  trend: 'services' },
  { name: 'Customers (legacy flat)',      url: '/customers',                 trend: 'customers' },
  { name: 'Customers (paginated 30)',     url: '/customers?limit=30',        trend: 'customers_paginated' },
  { name: 'Customers (search)',           url: '/customers?limit=30&search=fatih', trend: 'customers_search' },
  { name: 'Settings',                     url: '/settings',                  trend: null },
  { name: 'Users',                        url: '/users',                     trend: null },
  { name: 'Finance Summary',              url: '/finance/summary',           trend: null },
  { name: 'Expenses',                     url: '/expenses',                  trend: null },
  { name: 'Payroll',                      url: '/finance/payroll',           trend: null },
  { name: 'Current Plan',                 url: '/plan/current',             trend: null },
];

const trendMap = {
  dashboard: dashboardDuration,
  appointments: appointmentsDuration,
  services: servicesDuration,
  customers: customersDuration,
  customers_paginated: customersPagedDuration,
  customers_search: customersSearchDuration,
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