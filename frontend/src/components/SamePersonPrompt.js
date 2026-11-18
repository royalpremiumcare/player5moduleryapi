import { useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api from "../api/api";
import { formatApiError } from "../lib/apiError";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";

// Backend'in tekrar eden numara için döndürdüğü sabit mesaj (400).
export const DUPLICATE_PHONE_DETAIL = "Bu telefon numarasına sahip bir müşteri zaten var";

export const isDuplicatePhoneError = (error) =>
  error?.response?.status === 400 && error?.response?.data?.detail === DUPLICATE_PHONE_DETAIL;

// 905..., 05... ve 5... biçimleri aynı numara sayılsın diye son 10 hane karşılaştırılır.
const last10 = (phone) => String(phone || "").replace(/\D/g, "").slice(-10);

// Arama alt-dizge eşleşmesi yaptığı için sonuçlar arasından yalnızca aynı numarayı seç.
export function pickSameNumber(items, phone) {
  const wanted = last10(phone);
  if (wanted.length < 10) return null;
  return (items || []).find((c) => last10(c.phone) === wanted) || null;
}

// Mevcut kaydı bulmak için API sözleşmesini değiştirmeden numarayla arar.
export async function findExistingCustomer(phone) {
  const digits = String(phone || "").replace(/\D/g, "");
  const res = await api.get("/customers", { params: { search: digits, limit: 5 } });
  const items = Array.isArray(res.data?.items) ? res.data.items : [];
  return pickSameNumber(items, phone);
}

// Yeni müşteri eklenirken numara zaten kayıtlıysa "aynı kişi mi?" sorusu.
const SamePersonPrompt = ({ open, name, payload, onSame, onDone, onClose }) => {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);

  const handleDifferent = async () => {
    setBusy(true);
    try {
      const res = await api.post("/customers", { ...payload, allow_shared_phone: true });
      toast.success(res.data?.message || t("customers.addSuccess"));
      onDone();
    } catch (error) {
      toast.error(formatApiError(error, t, t("customers.addError")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o && !busy) onClose(); }}>
      <DialogContent className="backdrop-blur-2xl bg-white/95 border-white/30 rounded-3xl shadow-2xl sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="text-xl font-black text-zinc-900">
            {t("customers.samePerson.prompt", { name })}
          </DialogTitle>
          <DialogDescription className="sr-only">
            {t("customers.samePerson.prompt", { name })}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2 sm:gap-2">
          <Button type="button" variant="outline" disabled={busy} onClick={handleDifferent} className="rounded-xl font-bold">
            {t("customers.samePerson.different")}
          </Button>
          <Button type="button" disabled={busy} onClick={onSame} className="rounded-xl font-bold">
            {t("customers.samePerson.same")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default SamePersonPrompt;
