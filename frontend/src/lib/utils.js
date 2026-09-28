import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

/**
 * Radix modal içeriği için onInteractOutside sarmalayıcısı. Toaster body'de,
 * modalın dışında durduğundan toast'a dokunmak "dışarı tıklama" sayılıp modalı
 * (ve içindeki yarım formu) kapatıyordu.
 */
export function keepOpenOnToastInteract(handler) {
  return (event) => {
    if (event?.target?.closest?.("[data-sonner-toaster]")) {
      event.preventDefault()
      return
    }
    handler?.(event)
  }
}
