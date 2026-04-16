/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_APP_NAME?: string;
  /** Public site origin (no trailing slash), e.g. `https://polls.example.com` — baked at build for absolute `og:image`. */
  readonly VITE_PUBLIC_ORIGIN?: string;
  /** Optional URL for “OBS / browser source” doc link (My Polls, Poll owner kit, Home, Developer). */
  readonly VITE_STREAMING_OBS_DOC_URL?: string;
  /**
   * Footer line: **`default`** (or empty) = “Powered by” + link; **`hidden`** / **`none`** / **`off`** = no footer;
   * any other string = plain-text footer (max 280 chars), e.g. whitelabel stream credit.
   */
  readonly VITE_SITE_FOOTER?: string;
  /** Optional URL for the default footer link (`https:` only, or `http://localhost…`). */
  readonly VITE_ATTRIBUTION_URL?: string;
  /** Optional Umami script URL, e.g. `https://umami.example.com/script.js`. */
  readonly VITE_UMAMI_SCRIPT_URL?: string;
  /** Optional Umami website ID (UUID). Requires `VITE_UMAMI_SCRIPT_URL`. */
  readonly VITE_UMAMI_WEBSITE_ID?: string;
  /** Optional comma-separated hostnames for Umami `data-domains`. */
  readonly VITE_UMAMI_DOMAINS?: string;
  /** Optional Plausible script URL, e.g. `https://plausible.example.com/js/script.js`. */
  readonly VITE_PLAUSIBLE_SCRIPT_URL?: string;
  /** Optional Plausible site domain, e.g. `asking-ng.example.com`. */
  readonly VITE_PLAUSIBLE_DOMAIN?: string;
  /** Optional Matomo base URL, e.g. `https://matomo.example.com`. */
  readonly VITE_MATOMO_BASE_URL?: string;
  /** Optional Matomo site ID, e.g. `1`. */
  readonly VITE_MATOMO_SITE_ID?: string;
  /**
   * Legal / terms page (baked at **client build**): public contact email for abuse, copyright, and privacy requests.
   * Example: `abuse@example.com`
   */
  readonly VITE_LEGAL_CONTACT_EMAIL?: string;
  /**
   * Optional HTTPS URL for a contact or abuse-report form (shown on Terms if set).
   */
  readonly VITE_LEGAL_CONTACT_URL?: string;
  /**
   * Short label for governing law / venue, e.g. `State of California, USA` or `Ireland`.
   * Shown on Terms; omit for a generic fallback sentence.
   */
  readonly VITE_LEGAL_JURISDICTION?: string;
  /** ISO date or human-readable “last updated” line for Terms / Privacy (optional). */
  readonly VITE_LEGAL_LAST_UPDATED?: string;
  /** Optional security contact (defaults to VITE_LEGAL_CONTACT_EMAIL when unset). */
  readonly VITE_LEGAL_SECURITY_EMAIL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
