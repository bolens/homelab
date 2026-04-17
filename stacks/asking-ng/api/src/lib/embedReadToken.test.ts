import { describe, expect, it } from 'vitest';
import type { AppRequest } from '../types/http';
import {
  generateEmbedReadToken,
  hashEmbedReadToken,
  isPollOwnerRequest,
  pollEmbedReadAllowed,
  verifyEmbedReadToken,
} from './embedReadToken';

describe('embedReadToken', () => {
  it('verify passes when no hash is configured', () => {
    expect(verifyEmbedReadToken(null, undefined)).toBe(true);
    expect(verifyEmbedReadToken('', 'anything')).toBe(true);
  });

  it('round-trips hash verification', () => {
    const token = generateEmbedReadToken();
    const hash = hashEmbedReadToken(token);
    expect(verifyEmbedReadToken(hash, token)).toBe(true);
    expect(verifyEmbedReadToken(hash, `${token}x`)).toBe(false);
    expect(verifyEmbedReadToken(hash, undefined)).toBe(false);
  });

  it('isPollOwnerRequest matches creator id', () => {
    const req = { user: { id: 42 } } as AppRequest;
    expect(isPollOwnerRequest(req, 42)).toBe(true);
    expect(isPollOwnerRequest(req, 41)).toBe(false);
    expect(isPollOwnerRequest(req, null)).toBe(false);
    expect(isPollOwnerRequest({} as AppRequest, 42)).toBe(false);
  });

  it('pollEmbedReadAllowed accepts owner JWT when token missing', () => {
    const hash = hashEmbedReadToken('secret');
    const req = { user: { id: 7 } } as AppRequest;
    expect(pollEmbedReadAllowed(req, hash, undefined, 7)).toBe(true);
    expect(pollEmbedReadAllowed(req, hash, undefined, 8)).toBe(false);
    expect(pollEmbedReadAllowed({} as AppRequest, hash, undefined, 7)).toBe(false);
  });
});
