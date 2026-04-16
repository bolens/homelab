/** Default matches Navbar upstream; override with `VITE_STREAMING_OBS_DOC_URL` at client build time. */
const DEFAULT_HREF =
  'https://github.com/homelab-user/asking-ng/blob/main/stacks/asking-ng/docs/STREAMING-OBS-BROWSER-SOURCE.md';

export function streamingObsDocHref(): string {
  const fromEnv = import.meta.env.VITE_STREAMING_OBS_DOC_URL?.trim();
  return fromEnv && fromEnv.length > 0 ? fromEnv : DEFAULT_HREF;
}
