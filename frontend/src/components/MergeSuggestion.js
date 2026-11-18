import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api from "../api/api";
import { formatApiError } from "../lib/apiError";

// Liste satırında, aynı numaralı olası çift kayıt için "birleştir mi?" önerisi.
// Yalnız yöneticiye gösterilir (birleştirme yönetici işi); personel hiçbir şey görmez.
const MergeSuggestion = ({ customer, survivorName, userRole, onDone }) => {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [lookedUpName, setLookedUpName] = useState("");
  const survivorId = customer.merge_suggestion_for;
  const isAdmin = userRole === "admin";

  useEffect(() => {
    if (!isAdmin || survivorName) return undefined;
    let cancelled = false;
    const digits = String(customer.phone || "").replace(/\D/g, "");
    api.get("/customers", { params: { search: digits, limit: 5 } })
      .then((res) => {
        const match = (res.data?.items || []).find((c) => c.id === survivorId);
        if (!cancelled && match) setLookedUpName(match.name || "");
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [isAdmin, survivorName, survivorId, customer.phone]);

  const run = async (request, successKey) => {
    setBusy(true);
    try {
      await request();
      if (successKey) toast.success(t(successKey));
      onDone();
    } catch (error) {
      // 409 (yarış) ve 400 (numaralar farklı) için API'nin kendi mesajı gösterilir.
      toast.error(formatApiError(error, t, t("customers.addError")));
    } finally {
      setBusy(false);
    }
  };

  const merge = () => run(() => api.post("/customers/merge", { survivor_id: survivorId, source_id: customer.id }));
  const notDuplicate = () => run(() => api.post(`/customers/${customer.id}/not-duplicate`));
  const name = survivorName || lookedUpName;

  if (!isAdmin) return null;

  return (
    <div role="group" aria-label={t("customers.mergeSuggestion.prompt", { name })} className="mt-3 rounded-xl bg-amber-50 border border-amber-200 p-3">
      <p className="text-sm font-medium text-zinc-800">{t("customers.mergeSuggestion.prompt", { name })}</p>
      <div className="mt-2 flex gap-2">
        <button type="button" disabled={busy} onClick={merge} className="px-3 py-2 rounded-lg bg-zinc-900 text-white text-sm font-bold disabled:opacity-60">
          {t("customers.mergeSuggestion.merge")}
        </button>
        <button type="button" disabled={busy} onClick={notDuplicate} className="px-3 py-2 rounded-lg bg-white border border-zinc-300 text-zinc-800 text-sm font-bold disabled:opacity-60">
          {t("customers.mergeSuggestion.different")}
        </button>
      </div>
    </div>
  );
};

export default MergeSuggestion;
