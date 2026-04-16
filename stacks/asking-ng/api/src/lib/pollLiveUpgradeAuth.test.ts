import type { IncomingMessage } from 'node:http';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { generateToken } from '../utils/auth';
import { generateEmbedReadToken, hashEmbedReadToken } from './embedReadToken';
import {
  pollLiveUpgradeAllowed,
  readEmbedTokenFromUpgrade,
  readWsBearerFromUpgrade,
} from './pollLiveUpgradeAuth';

vi.mock('../models/user.sequelize', () => ({
  default: { findByPk: vi.fn() },
}));

import User from '../models/user.sequelize';

function req(headers: Record<string, string | string[] | undefined>): IncomingMessage {
  return { headers } as IncomingMessage;
}

describe('pollLiveUpgradeAuth', () => {
  beforeEach(() => {
    vi.mocked(User.findByPk).mockReset();
  });

  it('readEmbedTokenFromUpgrade prefers query then header', () => {
    const u = new URL('http://x/ws/poll/1?embed_token=q');
    expect(readEmbedTokenFromUpgrade(req({}), u)).toBe('q');
    const u2 = new URL('http://x/ws/poll/1');
    expect(readEmbedTokenFromUpgrade(req({ 'x-poll-embed-token': 'h' }), u2)).toBe('h');
  });

  it('readWsBearerFromUpgrade prefers query then Authorization', () => {
    const u = new URL('http://x/ws/poll/1?ws_bearer=j');
    expect(readWsBearerFromUpgrade(req({}), u)).toBe('j');
    const u2 = new URL('http://x/ws/poll/1');
    expect(readWsBearerFromUpgrade(req({ authorization: 'Bearer tok' }), u2)).toBe('tok');
  });

  it('pollLiveUpgradeAllowed accepts valid embed token', async () => {
    const tok = generateEmbedReadToken();
    const hash = hashEmbedReadToken(tok);
    await expect(
      pollLiveUpgradeAllowed({
        pollId: 'poll-1',
        url: new URL('http://x/ws/poll/poll-1'),
        embedReadTokenHash: hash,
        embedToken: tok,
        creatorUserId: 1,
        wsBearer: undefined,
      }),
    ).resolves.toBe(true);
  });

  it('pollLiveUpgradeAllowed accepts owner JWT when embed token missing', async () => {
    const hash = hashEmbedReadToken('secret');
    const jwt = generateToken({ id: 9, homelab-user: 'u', role: 'user' });
    vi.mocked(User.findByPk).mockResolvedValue({
      get: (k: string) => (k === 'active' ? true : undefined),
    } as never);
    await expect(
      pollLiveUpgradeAllowed({
        pollId: 'poll-1',
        url: new URL('http://x/ws/poll/poll-1'),
        embedReadTokenHash: hash,
        embedToken: undefined,
        creatorUserId: 9,
        wsBearer: jwt,
      }),
    ).resolves.toBe(true);
  });

  it('pollLiveUpgradeAllowed rejects wrong owner or inactive user', async () => {
    const hash = hashEmbedReadToken('secret');
    const jwt = generateToken({ id: 9, homelab-user: 'u', role: 'user' });
    vi.mocked(User.findByPk).mockResolvedValue({
      get: (k: string) => (k === 'active' ? true : undefined),
    } as never);
    await expect(
      pollLiveUpgradeAllowed({
        pollId: 'poll-1',
        url: new URL('http://x/ws/poll/poll-1'),
        embedReadTokenHash: hash,
        embedToken: undefined,
        creatorUserId: 8,
        wsBearer: jwt,
      }),
    ).resolves.toBe(false);

    vi.mocked(User.findByPk).mockResolvedValue({
      get: (k: string) => (k === 'active' ? false : undefined),
    } as never);
    await expect(
      pollLiveUpgradeAllowed({
        pollId: 'poll-1',
        url: new URL('http://x/ws/poll/poll-1'),
        embedReadTokenHash: hash,
        embedToken: undefined,
        creatorUserId: 9,
        wsBearer: jwt,
      }),
    ).resolves.toBe(false);
  });
});
