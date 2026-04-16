import AppSetting from '../models/appsettings.sequelize';

const SIGNUPS_ENABLED_KEY = 'signups_enabled';
const VOTE_GEO_ENABLED_KEY = 'vote_geo_enabled';

/** When the row is missing (e.g. mid-migration), signups stay allowed so existing installs are not locked out. */
export async function getSignupsEnabled(): Promise<boolean> {
  const row = await AppSetting.findByPk(SIGNUPS_ENABLED_KEY);
  if (!row) return true;
  return (row.get('value') as string) === 'true';
}

export async function setSignupsEnabled(enabled: boolean): Promise<void> {
  const now = new Date();
  await AppSetting.upsert({
    key: SIGNUPS_ENABLED_KEY,
    value: enabled ? 'true' : 'false',
    updatedAt: now,
  });
}

/** Missing row defaults to enabled for backward-compatible rollout. */
export async function getVoteGeoEnabled(): Promise<boolean> {
  const row = await AppSetting.findByPk(VOTE_GEO_ENABLED_KEY);
  if (!row) return true;
  return (row.get('value') as string) === 'true';
}

export async function setVoteGeoEnabled(enabled: boolean): Promise<void> {
  const now = new Date();
  await AppSetting.upsert({
    key: VOTE_GEO_ENABLED_KEY,
    value: enabled ? 'true' : 'false',
    updatedAt: now,
  });
}
