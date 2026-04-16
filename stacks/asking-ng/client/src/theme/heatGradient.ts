/**
 * Gradient stops for leaflet.heat, derived from CSS theme tokens on `<html>`.
 * Returns `undefined` when tokens are unavailable so leaflet.heat keeps its default gradient.
 */
export function readHeatGradientFromDocumentTheme(): Record<number, string> | undefined {
  if (typeof document === 'undefined') {
    return undefined;
  }
  const s = getComputedStyle(document.documentElement);
  const pick = (...names: string[]) => {
    for (const name of names) {
      const v = s.getPropertyValue(name).trim();
      if (v) return v;
    }
    return '';
  };
  const c0 = pick('--color-poll-fill-rest', '--color-border');
  const c1 = pick('--accent-control', '--color-focus-ring', '--color-border');
  const c2 = pick('--color-danger', '--color-success', '--accent-control');
  if (!c0 || !c1 || !c2) {
    return undefined;
  }
  return {
    0.2: c0,
    0.45: c1,
    0.72: c2,
    1: c2,
  };
}
