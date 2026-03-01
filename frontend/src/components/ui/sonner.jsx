import { useTheme } from "next-themes"
import { Toaster as Sonner, toast } from "sonner"

const Toaster = ({
  ...props
}) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme}
      className="toaster group"
      style={{
        '--offset': 'max(16px, env(safe-area-inset-top, 16px))',
      }}
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:backdrop-blur-xl group-[.toaster]:bg-white/80 group-[.toaster]:dark:bg-gray-900/80 group-[.toaster]:text-gray-900 group-[.toaster]:dark:text-white group-[.toaster]:border group-[.toaster]:border-white/30 group-[.toaster]:dark:border-white/10 group-[.toaster]:shadow-[0_8px_32px_rgba(0,0,0,0.12)] group-[.toaster]:rounded-2xl",
          description: "group-[.toast]:text-gray-600 group-[.toast]:dark:text-gray-300",
          actionButton:
            "group-[.toast]:bg-gray-900 group-[.toast]:text-white group-[.toast]:rounded-xl group-[.toast]:font-medium",
          cancelButton:
            "group-[.toast]:bg-white/50 group-[.toast]:text-gray-700 group-[.toast]:rounded-xl",
          success:
            "group-[.toaster]:!bg-emerald-50/90 group-[.toaster]:!border-emerald-200/50 group-[.toaster]:!text-emerald-900",
          error:
            "group-[.toaster]:!bg-red-50/90 group-[.toaster]:!border-red-200/50 group-[.toaster]:!text-red-900",
          info:
            "group-[.toaster]:!bg-blue-50/90 group-[.toaster]:!border-blue-200/50 group-[.toaster]:!text-blue-900",
        },
      }}
      {...props} />
  );
}

export { Toaster, toast }
