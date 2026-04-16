import { appEnv } from './env';

const PLATFORM_PROVIDERS = [
  'twitch',
  'youtube',
  'kick',
  'discord',
  'telegram',
  'slack',
  'x',
  'tiktok',
  'facebook',
  'instagram',
] as const;

export type PlatformProvider = (typeof PLATFORM_PROVIDERS)[number];

export function platformWebhooksEnabled(): boolean {
  return appEnv.enablePlatformWebhooks;
}

export function isPlatformProvider(value: string): value is PlatformProvider {
  return PLATFORM_PROVIDERS.includes(value as PlatformProvider);
}

export function platformProviders(): readonly PlatformProvider[] {
  return PLATFORM_PROVIDERS;
}

export function platformWebhookSharedSecret(): string {
  return appEnv.platformWebhookSharedSecret;
}
