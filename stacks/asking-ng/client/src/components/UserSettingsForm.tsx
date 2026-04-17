import { useEffect, useState } from 'react';
import { useT, useUILocale } from '../i18n/I18nContext';
import { type MessageKey, UI_LOCALES, type UILocale } from '../i18n/locales';
import {
  COLOR_THEME_EVENT,
  COLOR_THEME_IDS,
  COLOR_THEME_STORAGE_KEY,
  type ColorThemeId,
  readStoredThemeId,
  setColorTheme,
} from '../theme/colorTheme';
import {
  HIGH_CONTRAST_EVENT,
  HIGH_CONTRAST_STORAGE_KEY,
  readStoredHighContrast,
  setHighContrast,
} from '../theme/highContrast';
import {
  COLOR_VISION_IDS,
  COLOR_VISION_STORAGE_KEY,
  type ColorVisionId,
  DYSLEXIA_MODE_IDS,
  DYSLEXIA_MODE_STORAGE_KEY,
  type DyslexiaModeId,
  READING_COMFORT_EVENT,
  readStoredColorVision,
  readStoredDyslexiaMode,
  setColorVision,
  setDyslexiaMode,
} from '../theme/readingComfort';
import { Checkbox, FormRow, Select, Stack } from '../ui';

const CVD_LABEL_KEY: Record<ColorVisionId, MessageKey> = {
  none: 'nav.colorVision.none',
  protanopia: 'nav.colorVision.protanopia',
  deuteranopia: 'nav.colorVision.deuteranopia',
  tritanopia: 'nav.colorVision.tritanopia',
  monochrome: 'nav.colorVision.monochrome',
};

const DYSLEXIA_LABEL_KEY: Record<DyslexiaModeId, MessageKey> = {
  off: 'nav.readingComfort.off',
  readable: 'nav.readingComfort.readable',
  lexend: 'nav.readingComfort.lexend',
  hyperlegible: 'nav.readingComfort.hyperlegible',
  inter: 'nav.readingComfort.inter',
  geist: 'nav.readingComfort.geist',
  'ibm-plex': 'nav.readingComfort.ibmPlex',
  'dm-sans': 'nav.readingComfort.dmSans',
  'plus-jakarta': 'nav.readingComfort.plusJakarta',
  'source-sans-3': 'nav.readingComfort.sourceSans3',
  'nf-jetbrains': 'nav.readingComfort.nfJetbrains',
  'nf-fira': 'nav.readingComfort.nfFira',
  'nf-hack': 'nav.readingComfort.nfHack',
  'nf-meslo': 'nav.readingComfort.nfMeslo',
  'nf-cascadia': 'nav.readingComfort.nfCascadia',
  'nf-ubuntu': 'nav.readingComfort.nfUbuntu',
  'nf-iosevka': 'nav.readingComfort.nfIosevka',
};

const UI_LOCALE_LABEL_KEY: Record<UILocale, MessageKey> = {
  'en-us': 'nav.locale.en-us',
  'en-gb': 'nav.locale.en-gb',
  fr: 'nav.locale.fr',
  es: 'nav.locale.es',
  ga: 'nav.locale.ga',
  de: 'nav.locale.de',
  it: 'nav.locale.it',
};

const THEME_LABEL_KEY: Record<ColorThemeId, MessageKey> = {
  system: 'nav.theme.system',
  light: 'nav.theme.light',
  dark: 'nav.theme.dark',
  dracula: 'nav.theme.dracula',
  'solarized-dark': 'nav.theme.solarized-dark',
  'solarized-light': 'nav.theme.solarized-light',
  nord: 'nav.theme.nord',
  'gruvbox-dark': 'nav.theme.gruvbox-dark',
  'gruvbox-light': 'nav.theme.gruvbox-light',
  'catppuccin-mocha': 'nav.theme.catppuccin-mocha',
  'tokyo-night': 'nav.theme.tokyo-night',
};

type UserSettingsFormProps = {
  /** Extra class on the outer wrapper (e.g. modal body). */
  className?: string;
};

export default function UserSettingsForm({ className }: UserSettingsFormProps) {
  const t = useT();
  const { uiLocale, setUILocale } = useUILocale();
  const [colorTheme, setColorThemeState] = useState<ColorThemeId>(() => readStoredThemeId());
  const [colorVision, setColorVisionState] = useState<ColorVisionId>(() => readStoredColorVision());
  const [dyslexiaMode, setDyslexiaModeState] = useState<DyslexiaModeId>(() =>
    readStoredDyslexiaMode(),
  );
  const [highContrast, setHighContrastState] = useState(() => readStoredHighContrast());

  useEffect(() => {
    const sync = () => setColorThemeState(readStoredThemeId());
    window.addEventListener(COLOR_THEME_EVENT, sync);
    const onStorage = (e: StorageEvent) => {
      if (e.key != null && e.key !== COLOR_THEME_STORAGE_KEY) return;
      sync();
    };
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener(COLOR_THEME_EVENT, sync);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  useEffect(() => {
    const syncComfort = () => {
      setColorVisionState(readStoredColorVision());
      setDyslexiaModeState(readStoredDyslexiaMode());
    };
    window.addEventListener(READING_COMFORT_EVENT, syncComfort);
    const onStorage = (e: StorageEvent) => {
      if (
        e.key != null &&
        e.key !== COLOR_VISION_STORAGE_KEY &&
        e.key !== DYSLEXIA_MODE_STORAGE_KEY
      ) {
        return;
      }
      syncComfort();
    };
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener(READING_COMFORT_EVENT, syncComfort);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  useEffect(() => {
    const syncHc = () => setHighContrastState(readStoredHighContrast());
    window.addEventListener(HIGH_CONTRAST_EVENT, syncHc);
    const onStorage = (e: StorageEvent) => {
      if (e.key != null && e.key !== HIGH_CONTRAST_STORAGE_KEY) return;
      syncHc();
    };
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener(HIGH_CONTRAST_EVENT, syncHc);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  return (
    <div className={className}>
      <Stack gap='md'>
        <FormRow label={t('nav.languageLabel')} htmlFor='asking-settings-page__ui-locale'>
          <Select
            id='asking-settings-page__ui-locale'
            className='ui-input--stack'
            value={uiLocale}
            onChange={(e) => setUILocale(e.target.value as UILocale)}
            aria-label={t('nav.languageLabel')}
          >
            {UI_LOCALES.map((id) => (
              <option key={id} value={id}>
                {t(UI_LOCALE_LABEL_KEY[id])}
              </option>
            ))}
          </Select>
        </FormRow>
        <FormRow label={t('nav.themeLabel')} htmlFor='asking-settings-page__color-theme'>
          <Select
            id='asking-settings-page__color-theme'
            className='ui-input--stack'
            value={colorTheme}
            onChange={(e) => {
              const id = e.target.value as ColorThemeId;
              setColorTheme(id);
            }}
            aria-label={t('nav.themeLabel')}
          >
            {COLOR_THEME_IDS.map((id) => (
              <option key={id} value={id}>
                {t(THEME_LABEL_KEY[id])}
              </option>
            ))}
          </Select>
        </FormRow>
        <FormRow label={t('nav.colorVisionLabel')} htmlFor='asking-settings-page__color-vision'>
          <Select
            id='asking-settings-page__color-vision'
            className='ui-input--stack'
            value={colorVision}
            onChange={(e) => {
              const id = e.target.value as ColorVisionId;
              setColorVision(id);
            }}
            aria-label={t('nav.colorVisionLabel')}
          >
            {COLOR_VISION_IDS.map((id) => (
              <option key={id} value={id}>
                {t(CVD_LABEL_KEY[id])}
              </option>
            ))}
          </Select>
        </FormRow>
        <FormRow label={t('nav.readingComfortLabel')} htmlFor='asking-settings-page__reading-comfort'>
          <Select
            id='asking-settings-page__reading-comfort'
            className='ui-input--stack'
            value={dyslexiaMode}
            onChange={(e) => {
              const id = e.target.value as DyslexiaModeId;
              setDyslexiaMode(id);
            }}
            aria-label={t('nav.readingComfortLabel')}
          >
            {DYSLEXIA_MODE_IDS.map((id) => (
              <option key={id} value={id}>
                {t(DYSLEXIA_LABEL_KEY[id])}
              </option>
            ))}
          </Select>
        </FormRow>
        <Checkbox
          id='asking-settings-page__high-contrast'
          label={t('nav.highContrast')}
          checked={highContrast}
          onChange={(e) => setHighContrast(e.target.checked)}
        />
      </Stack>
    </div>
  );
}
