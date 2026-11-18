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

// Mevcut kaydı bulmak için API sözleşmesini değiştirmeden numarayla arar.
export async function findExistingCustomer(phone) {
  const digits = String(phone || "").replace(/\D/g, "");
  const res = await api.get("/customers", { params: { search: digits, limit: 5 } });
  const items = Array.isArray(res.data?.items) ? res.data.items : [];
  return items[0] || null;
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
