# MOBİL API SURFACE — Donmuş Build Sözleşme Yüzeyi

> **AMAÇ:** App Store / Play Store'daki DONMUŞ mobil build (Capacitor, aynı React bundle)
> aşağıdaki endpoint'leri çağırır. Bu endpoint'lerin **response ŞEKLİNİ** değiştirmek
> (alan silme/rename/tip/anlam değişimi, array→obje) sahadaki uygulamayı SESSİZCE kırar.
> Bir endpoint'e dokunmadan önce burada olup olmadığını kontrol et; buradaysa additive-only
> kuralına uy ve `backend/tests/integration/` contract testlerini çalıştır.
>
> Bu liste `frontend/src` içindeki `api.*()` / `publicApi.*()` çağrılarından OTOMATİK üretilir.
> Yenilemek için `backend/tests/contracts/gen_mobile_surface.sh` çalıştır.
>
> NOT: Liste tüm frontend bundle'ını kapsar (merchant + superadmin + marketing). Hepsi aynı
> bundle'da olduğu için hepsi potansiyel donmuş yüzeydir.

## Endpoint listesi (auto)

```
GET    /admin/staff/{param}/breaks
POST   /admin/staff/{param}/breaks
DELETE /admin/staff/{param}/breaks/{param}
POST   /ai/chat
GET    /appointments
POST   /appointments
POST   /appointments/bulk-package
POST   /appointments/bulk-session
POST   /appointments/cancel-selected
DELETE /appointments/groups/{param}
DELETE /appointments/{param}
PUT    /appointments/{param}
POST   /appointments/{param}/refund
GET    /audit-logs
POST   /auth/setup-password
GET    /availability
POST   /availability/bulk-check
GET    /categories
POST   /categories
POST   /categories/reorder
DELETE /categories/{param}
PUT    /categories/{param}
POST   /contact
GET    /customers
POST   /customers
DELETE /customers/{param}
PUT    /customers/{param}
GET    /customers/{param}/history
PUT    /customers/{param}/notes
GET    /expenses
POST   /expenses
DELETE /expenses/{param}
GET    /finance/payroll
POST   /finance/payroll/payment
GET    /finance/summary
POST   /forgot-password
GET    /marketing/autopilot
PUT    /marketing/autopilot
GET    /marketing/leads
GET    /marketing/leads/batches
GET    /marketing/leads/sectors
POST   /marketing/leads/{param}/claim
POST   /marketing/leads/{param}/release
PUT    /marketing/leads/{param}/status
GET    /marketing/my-stats
GET    /marketing/organizations
GET    /marketing/profile
GET    /me/chatwoot-identity
GET    /merchant/customers/search
GET    /merchant/features
POST   /merchant/payment-links
GET    /merchant/payment-settings
PUT    /merchant/payment-settings
GET    /merchant/payout/history
POST   /merchant/payout/request
POST   /merchant/refund-requests
GET    /merchant/refund-requests{param}
GET    /merchant/transactions
GET    /merchant/wallet
GET    /merchant/wallet/status
POST   /meta/event
POST   /onboarding/add-service
POST   /onboarding/aha-skip
POST   /onboarding/aha-test-appointment
POST   /onboarding/complete
GET    /onboarding/info
POST   /onboarding/update-hours
POST   /onboarding/update-services
POST   /payments/confirm-checkout-session
POST   /payments/create-checkout-session
GET    /plan/current
GET    /plans
POST   /public/appointments
GET    /public/availability/{param}
GET    /public/business/{param}
POST   /public/checkout
GET    /public/fee-preview
POST   /public/verify-code
GET    /public/verify-status
POST   /push/debug
GET    /push/status
POST   /push/subscribe
DELETE /push/unsubscribe
GET    /push/vapid-key
POST   /register-initiate
POST   /register-verify
GET    /services
POST   /services
POST   /services/reorder
DELETE /services/{param}
PUT    /services/{param}
POST   /sessions/wave-plan
GET    /settings
PUT    /settings
DELETE /settings/location
POST   /settings/logo
POST   /sso/create
POST   /staff/add
GET    /staff/breaks
POST   /staff/breaks
DELETE /staff/breaks/{param}
DELETE /staff/{param}
PUT    /staff/{param}/days-off
PUT    /staff/{param}/payment
PUT    /staff/{param}/services
PUT    /staff/{param}/toggle-permission
GET    /stats/dashboard
GET    /stats/personnel
POST   /subscription/portal
POST   /superadmin/broadcast-email
POST   /superadmin/broadcast-push
GET    /superadmin/contact-requests
DELETE /superadmin/contact-requests/bulk/delete-resolved
DELETE /superadmin/contact-requests/{param}
PUT    /superadmin/contact-requests/{param}/status
GET    /superadmin/financial-stats
GET    /superadmin/financial/audit/summary
GET    /superadmin/financial/audit/transaction/{param}
GET    /superadmin/financial/audit/transactions
GET    /superadmin/financial/batches/awaiting
POST   /superadmin/financial/batches/bulk-confirm-fund
POST   /superadmin/financial/batches/bulk-prepare-wise
POST   /superadmin/financial/batches/{param}/confirm-fund
POST   /superadmin/financial/batches/{param}/mark-failed
POST   /superadmin/financial/batches/{param}/prepare-wise
POST   /superadmin/financial/dlq/{param}/abandon
POST   /superadmin/financial/dlq/{param}/resolve
POST   /superadmin/financial/dlq/{param}/retry
GET    /superadmin/financial/dlq{param}
GET    /superadmin/financial/feature-flags
POST   /superadmin/financial/feature-flags/{param}/global
POST   /superadmin/financial/feature-flags/{param}/kill-switch
POST   /superadmin/financial/kyc/{param}/verify
GET    /superadmin/financial/overview
GET    /superadmin/financial/reconciliation/discrepancies
GET    /superadmin/financial/reconciliation/export.{param}
GET    /superadmin/financial/reconciliation/multi_summary
DELETE /superadmin/financial/wallet/{param}
POST   /superadmin/financial/wallet/{param}/freeze
GET    /superadmin/financial/wallets
GET    /superadmin/leads
DELETE /superadmin/leads/batch/{param}
GET    /superadmin/leads/batches
GET    /superadmin/leads/stats
POST   /superadmin/leads/upload/confirm
POST   /superadmin/leads/upload/preview
GET    /superadmin/organizations
DELETE /superadmin/organizations/{param}
POST   /superadmin/organizations/{param}/assign-plan
PATCH  /superadmin/organizations/{param}/internal
GET    /superadmin/organizations/{param}/staff
DELETE /superadmin/organizations/{param}/staff/{param}
GET    /superadmin/plans
GET    /superadmin/push/subscriber-counts
GET    /superadmin/refund-requests
GET    /superadmin/refund-requests/history
POST   /superadmin/refund-requests/{param}/approve
POST   /superadmin/refund-requests/{param}/reject
GET    /superadmin/stats
GET    /superadmin/users/marketing
POST   /superadmin/users/marketing
DELETE /superadmin/users/marketing/{param}
GET    /superadmin/whatsapp-logs
GET    /transactions
DELETE /transactions/{param}
PUT    /transactions/{param}
POST   /upload/image
GET    /users
PUT    /users/me

# TOPLAM: 169 distinct endpoint
```
