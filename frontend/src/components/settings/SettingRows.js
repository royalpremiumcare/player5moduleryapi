import { ChevronRight } from "lucide-react";

// Tıklanabilir satır klavye/VoiceOver için buton gibi davranır (native <button> gibi):
// Enter keydown'da, Space keyup'ta tetikler; Space keydown sayfayı kaydırmasın diye engellenir.
// Satırın içindeki bir kontrolde (ör. Switch) basılan tuşlar satırı tetiklemez.
const pressableProps = (onClick) => {
  if (!onClick) return {};
  const isOwnKey = (e) => e.target === e.currentTarget;
  return {
    role: "button",
    tabIndex: 0,
    onKeyDown: (e) => {
      if (!isOwnKey(e)) return;
      if (e.key === "Enter") onClick(e);
      else if (e.key === " ") e.preventDefault();
    },
    onKeyUp: (e) => {
      if (isOwnKey(e) && e.key === " ") onClick(e);
    },
  };
};

// --- YARDIMCI BİLEŞEN: AYAR SATIRI ---
// Tasarım Dili: Minimalist & Kurumsal
export const SettingItem = ({ 
  icon: Icon, 
  title, 
  subtitle, 
  onClick, 
  rightElement, 
  isDestructive = false,
  className = ""
}) => (
  <div 
    onClick={onClick} 
    {...pressableProps(onClick)}
    className={`flex items-center justify-between p-5 bg-white active:bg-zinc-50 transition-colors cursor-pointer first:rounded-t-2xl last:rounded-b-2xl border-b last:border-0 border-zinc-100 ${className}`}
  >
    <div className="flex items-center gap-4">
      {/* İkon Alanı: Renkli yerine "Kurumsal Gri" ve Çerçeveli */}
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 border shadow-sm ${
        isDestructive 
          ? 'bg-red-50 border-red-100 text-red-600' 
          : 'bg-zinc-50 border-zinc-200 text-zinc-600'
      }`}>
        <Icon className="w-6 h-6" strokeWidth={1.5} />
      </div>
      
      <div>
        <p className={`text-base font-medium ${isDestructive ? 'text-red-600' : 'text-zinc-900'}`}>
          {title}
        </p>
        {subtitle && <p className="text-sm text-zinc-500 mt-0.5">{subtitle}</p>}
      </div>
    </div>
    <div className="pl-3">
      {rightElement || <ChevronRight className="w-5 h-5 text-zinc-300" />}
    </div>
  </div>
);

// --- YARDIMCI BİLEŞEN: KATEGORİ BAŞLIĞI ---
export const SectionTitle = ({ title }) => (
  <h3 className="px-5 mb-3 mt-8 text-sm font-bold text-zinc-400 uppercase tracking-widest">
    {title}
  </h3>
);
