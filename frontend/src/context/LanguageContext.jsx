import { createContext, useContext, useState, useCallback, useMemo } from "react";
import { translations, LANGUAGES } from "../i18n/translations";

const LANG_KEY = "crm_lang";
const LanguageContext = createContext(null);

function getInitialLang() {
  const stored = localStorage.getItem(LANG_KEY);
  return LANGUAGES.some((l) => l.code === stored) ? stored : "en";
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(getInitialLang);

  const setLang = useCallback((code) => {
    localStorage.setItem(LANG_KEY, code);
    setLangState(code);
  }, []);

  const t = useCallback(
    (key) => {
      const parts = key.split(".");
      let node = translations[lang];
      for (const p of parts) node = node?.[p];
      if (node === undefined) {
        // Fall back to English, then to the raw key, rather than rendering "undefined" —
        // covers any string not yet translated for the current language.
        let fallback = translations.en;
        for (const p of parts) fallback = fallback?.[p];
        return fallback ?? key;
      }
      return node;
    },
    [lang]
  );

  const value = useMemo(() => ({ lang, setLang, t, languages: LANGUAGES }), [lang, setLang, t]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  return useContext(LanguageContext);
}
