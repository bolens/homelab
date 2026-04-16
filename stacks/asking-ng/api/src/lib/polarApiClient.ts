import { Polar } from '@polar-sh/sdk';
import { appEnv } from './env';

/** Server-to-server Polar API client (Organization Access Token). */
export function createPolarServerClient(): Polar | null {
  const token = appEnv.polarAccessToken?.trim();
  if (!token) return null;
  return new Polar({
    accessToken: token,
    server: appEnv.polarServer === 'sandbox' ? 'sandbox' : 'production',
  });
}
