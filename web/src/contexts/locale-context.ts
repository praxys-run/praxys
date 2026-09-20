import { createContext, useContext } from 'react';
import type { SupportedLocale } from '../i18n/init';

interface LocaleContextValue {
  locale: SupportedLocale;
  setLocale: (locale: SupportedLocale) => Promise<void>;
}
export const LocaleContext = createContext<LocaleContextValue>({ locale: 'en', setLocale: async () => {} });
export function useLocale() { return useContext(LocaleContext); }
