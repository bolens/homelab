import { useRouterState } from '@tanstack/react-router';

/** Pure helper for tests and {@link useRelativeLocationPath}. */
export function relativePathFromLocation(pathname: string, baseUrl: string): string {
  const base = String(baseUrl || '/').replace(/\/$/, '');
  if (base && pathname.startsWith(base)) {
    const tail = pathname.slice(base.length);
    if (tail === '' || tail === '/') return '/';
    return tail.startsWith('/') ? tail : `/${tail}`;
  }
  return pathname || '/';
}

/**
 * Location pathname relative to `import.meta.env.BASE_URL` (leading slash, `/` for index).
 */
export function useRelativeLocationPath(): string {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return relativePathFromLocation(pathname, String(import.meta.env.BASE_URL));
}
