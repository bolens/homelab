const readEnv = (env: ImportMetaEnv, key: keyof ImportMetaEnv): string =>
  String(env[key] || '').trim();

/**
 * Injects Umami analytics script when both script URL + website ID are provided.
 * No-op by default, so stacks can opt in without code changes.
 */
export const initUmami = (env: ImportMetaEnv = import.meta.env): void => {
  if (typeof document === 'undefined') return;

  const scriptUrl = readEnv(env, 'VITE_UMAMI_SCRIPT_URL');
  const websiteId = readEnv(env, 'VITE_UMAMI_WEBSITE_ID');
  const domains = readEnv(env, 'VITE_UMAMI_DOMAINS');

  if (!scriptUrl || !websiteId) return;
  if (document.querySelector('script[data-asking-ng-umami="1"]')) return;

  let resolvedScriptUrl = scriptUrl;
  try {
    resolvedScriptUrl = new URL(scriptUrl, window.location.origin).toString();
  } catch {
    return;
  }

  const script = document.createElement('script');
  script.defer = true;
  script.async = true;
  script.src = resolvedScriptUrl;
  script.setAttribute('data-website-id', websiteId);
  script.setAttribute('data-asking-ng-umami', '1');
  if (domains) script.setAttribute('data-domains', domains);
  document.head.appendChild(script);
};

export const initPlausible = (env: ImportMetaEnv = import.meta.env): void => {
  if (typeof document === 'undefined') return;
  const scriptUrl = readEnv(env, 'VITE_PLAUSIBLE_SCRIPT_URL');
  const domain = readEnv(env, 'VITE_PLAUSIBLE_DOMAIN');
  if (!scriptUrl || !domain) return;
  if (document.querySelector('script[data-asking-ng-plausible="1"]')) return;
  const script = document.createElement('script');
  script.defer = true;
  script.src = scriptUrl;
  script.setAttribute('data-domain', domain);
  script.setAttribute('data-asking-ng-plausible', '1');
  document.head.appendChild(script);
};

export const initMatomo = (env: ImportMetaEnv = import.meta.env): void => {
  if (typeof window === 'undefined' || typeof document === 'undefined') return;
  const baseUrlRaw = readEnv(env, 'VITE_MATOMO_BASE_URL');
  const siteId = readEnv(env, 'VITE_MATOMO_SITE_ID');
  if (!baseUrlRaw || !siteId) return;
  const baseUrl = `${baseUrlRaw.replace(/\/$/, '')}/`;
  const key = '__askingNgMatomoLoaded';
  if ((window as unknown as Record<string, unknown>)[key]) return;
  (window as unknown as Record<string, unknown>)[key] = true;

  const w = window as unknown as { _paq?: unknown[] };
  const paq = (w._paq = w._paq || []);
  paq.push(['trackPageView']);
  paq.push(['enableLinkTracking']);
  paq.push(['setTrackerUrl', `${baseUrl}matomo.php`]);
  paq.push(['setSiteId', siteId]);

  const script = document.createElement('script');
  script.async = true;
  script.src = `${baseUrl}matomo.js`;
  script.setAttribute('data-asking-ng-matomo', '1');
  document.head.appendChild(script);
};

export const initAnalyticsIntegrations = (env: ImportMetaEnv = import.meta.env): void => {
  initUmami(env);
  initPlausible(env);
  initMatomo(env);
};
