import { useEffect, useState } from 'react';

/**
 * useDebounce — bir değeri belirtilen gecikmeyle debounce eder.
 *
 * Kullanım:
 *   const debounced = useDebounce(searchTerm, 300);
 *
 * Kullanıcı 300 ms boyunca yeni bir tuşa basmazsa, `debounced` en son değere
 * eşitlenir. API çağrılarını her keystroke'ta değil, kullanıcı yazmayı
 * bıraktığında tetiklemek için ideal.
 */
export default function useDebounce(value, delay = 300) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
