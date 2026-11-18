import { useTranslation } from "react-i18next";
import { ArrowLeft, Wrench } from "lucide-react";

/** Shown instead of the Wallet and Payment Settings pages while merchant payments are paused. */
export default function PaymentsPausedNotice({ onNavigate }) {
  const { t } = useTranslation();
  return (
    <div className="p-4 pb-24 max-w-lg mx-auto space-y-5">
      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-label={t("paymentsPaused.back")}
          onClick={() => onNavigate && onNavigate("settings")}
          className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <ArrowLeft className="h-5 w-5 text-gray-600" aria-hidden="true" />
        </button>
      </div>
      <div className="rounded-2xl border border-gray-200 bg-white p-6 text-center">
        <div className="mx-auto mb-4 w-12 h-12 rounded-full bg-amber-50 flex items-center justify-center">
          <Wrench className="h-6 w-6 text-amber-600" aria-hidden="true" />
        </div>
        <h1 className="text-xl font-bold text-gray-900 mb-2">{t("paymentsPaused.title")}</h1>
        <p className="text-gray-600 leading-relaxed">{t("paymentsPaused.body")}</p>
        <p className="text-gray-600 leading-relaxed mt-3">{t("paymentsPaused.later")}</p>
      </div>
    </div>
  );
}
