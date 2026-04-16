import React, {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  CATALOGS,
  interpolate,
  type MessageKey,
  readStoredUILocale,
  UI_LOCALE_STORAGE_KEY,
  type UILocale,
} from './locales';

type Locale = UILocale;

type TFn = (key: MessageKey, vars?: Record<string, string | number>) => string;

type I18nContextValue = {
  locale: Locale;
  uiLocale: UILocale;
  localeTag: string;
  t: TFn;
  setUILocale: (next: UILocale) => void;
};

const I18nContext = createContext<I18nContextValue | null>(null);

function readNavigatorLanguageTag(): string {
  if (typeof navigator === 'undefined' || !navigator.language) return 'en';
  return navigator.language;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [uiLocale, setUiLocaleState] = useState<UILocale>(() => readStoredUILocale());
  const [localeTag, setLocaleTag] = useState(readNavigatorLanguageTag);

  const messages = CATALOGS[uiLocale];

  useEffect(() => {
    const onLanguageChange = () => setLocaleTag(readNavigatorLanguageTag());
    window.addEventListener('languagechange', onLanguageChange);
    return () => window.removeEventListener('languagechange', onLanguageChange);
  }, []);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.documentElement.lang = uiLocale;
  }, [uiLocale]);

  const setUILocale = useCallback((next: UILocale) => {
    setUiLocaleState(next);
    try {
      localStorage.setItem(UI_LOCALE_STORAGE_KEY, next);
    } catch {
      /* private mode / quota */
    }
  }, []);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key !== UI_LOCALE_STORAGE_KEY) return;
      setUiLocaleState(readStoredUILocale());
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const t = useCallback<TFn>(
    (key, vars) => {
      const raw = messages[key];
      if (raw === undefined) return String(key);
      return vars ? interpolate(raw, vars) : raw;
    },
    [messages],
  );

  const value = useMemo(
    () => ({
      locale: uiLocale,
      uiLocale,
      localeTag,
      t,
      setUILocale,
    }),
    [localeTag, t, uiLocale, setUILocale],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useT(): TFn {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error('useT must be used within I18nProvider');
  }
  return ctx.t;
}

/**
 * BCP 47 tag for `Intl`, aligned with selected UI locale.
 */
export function useLocaleTag(): string {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error('useLocaleTag must be used within I18nProvider');
  }
  if (ctx.uiLocale === 'en-us') return 'en-US';
  if (ctx.uiLocale === 'en-gb') return 'en-GB';
  return ctx.uiLocale;
}

/** Active UI string catalog (`en`, …) and setter (persists to {@link UI_LOCALE_STORAGE_KEY}). */
export function useUILocale(): { uiLocale: UILocale; setUILocale: (next: UILocale) => void } {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error('useUILocale must be used within I18nProvider');
  }
  return { uiLocale: ctx.uiLocale, setUILocale: ctx.setUILocale };
}
