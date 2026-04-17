import { DataTypes } from 'sequelize';
import db from '../connections';

const Poll = db.define('poll', {
  id: { primaryKey: true, type: DataTypes.STRING },
  title: DataTypes.STRING,
  options: DataTypes.ARRAY(DataTypes.STRING),
  expiration: DataTypes.BIGINT,
  limit_ip: DataTypes.BOOLEAN,
  api_key: DataTypes.STRING,
  archived: { type: DataTypes.BOOLEAN, allowNull: false, defaultValue: false },
  creatorUserId: { type: DataTypes.INTEGER, allowNull: true },
  workspaceId: { type: DataTypes.INTEGER, allowNull: true, field: 'workspace_id' },
  webhookTargets: { type: DataTypes.JSONB, allowNull: false, defaultValue: [] },
  phase: { type: DataTypes.STRING(16), allowNull: false, defaultValue: 'open' },
  votingPaused: { type: DataTypes.BOOLEAN, allowNull: false, defaultValue: false },
  pauseMessage: { type: DataTypes.STRING(280), allowNull: true },
  showNotes: { type: DataTypes.TEXT, allowNull: true },
  sharedEditorUserIds: { type: DataTypes.JSONB, allowNull: false, defaultValue: [] },
  mediaAttachment: { type: DataTypes.JSONB, allowNull: true },
  mediaBlurByDefault: { type: DataTypes.BOOLEAN, allowNull: false, defaultValue: true },
  mediaModeration: { type: DataTypes.JSONB, allowNull: false, defaultValue: { status: 'active' } },
  themePreset: { type: DataTypes.STRING(24), allowNull: false, defaultValue: 'default' },
  /** single: one choice per ballot; multi: multiple fixed options, one DB row per selected option. */
  selectionMode: { type: DataTypes.STRING(8), allowNull: false, defaultValue: 'single' },
  /** anonymous: public voting; account/platform_linked: JWT required, one ballot per user id. */
  voteEligibility: { type: DataTypes.STRING(16), allowNull: false, defaultValue: 'anonymous' },
  /** Provider key for platform-linked identity mode (scaffold metadata). */
  platformIdentityProvider: { type: DataTypes.STRING(64), allowNull: true },
  /** Consent/policy copy version acknowledged for identity-linked voting. */
  platformIdentityConsentVersion: { type: DataTypes.STRING(64), allowNull: true },
  /** UTC epoch ms when consent metadata was captured/updated. */
  platformIdentityConsentCapturedAt: { type: DataTypes.BIGINT, allowNull: true },
  impressionCount: { type: DataTypes.INTEGER, allowNull: false, defaultValue: 0 },
  impressionAttribution: { type: DataTypes.JSONB, allowNull: false, defaultValue: {} },
  viewEventsByHour: { type: DataTypes.JSONB, allowNull: false, defaultValue: {} },
  embedReadTokenHash: { type: DataTypes.STRING(64), allowNull: true },
  openAt: { type: DataTypes.BIGINT, allowNull: true },
  lockAt: { type: DataTypes.BIGINT, allowNull: true },
  revealAt: { type: DataTypes.BIGINT, allowNull: true },
  boostedVotingEnabled: { type: DataTypes.BOOLEAN, allowNull: false, defaultValue: false },
  maxBoostWeight: { type: DataTypes.INTEGER, allowNull: false, defaultValue: 3 },
  showUnweightedValues: { type: DataTypes.BOOLEAN, allowNull: false, defaultValue: false },
  runOfShowKey: { type: DataTypes.STRING(64), allowNull: true },
  runOfShowOrder: { type: DataTypes.INTEGER, allowNull: true },
  vanitySlug: { type: DataTypes.STRING(64), allowNull: true },
  nextPollId: { type: DataTypes.STRING, allowNull: true },
  autoAdvanceOnClose: { type: DataTypes.BOOLEAN, allowNull: false, defaultValue: false },
  voteFrictionTier: { type: DataTypes.STRING(24), allowNull: false, defaultValue: 'open' },
  softThrottleMaxVotesPerMin: { type: DataTypes.INTEGER, allowNull: false, defaultValue: 30 },
  powDifficulty: { type: DataTypes.INTEGER, allowNull: false, defaultValue: 4 },
  allowWriteIn: { type: DataTypes.BOOLEAN, allowNull: false, defaultValue: false },
  writeInMaxLength: { type: DataTypes.INTEGER, allowNull: false, defaultValue: 80 },
  writeInBlocklist: { type: DataTypes.ARRAY(DataTypes.STRING), allowNull: false, defaultValue: [] },
  writeInProfanityFilter: { type: DataTypes.BOOLEAN, allowNull: false, defaultValue: true },
  resultsDelaySeconds: { type: DataTypes.INTEGER, allowNull: false, defaultValue: 0 },
  retentionTtlDays: { type: DataTypes.INTEGER, allowNull: true },
  retentionLegalHold: { type: DataTypes.BOOLEAN, allowNull: false, defaultValue: false },
});

export default Poll;
