const DEFAULT_PROFANITY_TERMS = ['fuck', 'shit', 'bitch', 'asshole', 'motherfucker', 'nigger'];

function normalizeToken(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '');
}

function containsBlockedToken(text: string, terms: readonly string[]): string | null {
  const normalizedText = normalizeToken(text);
  for (const term of terms) {
    const t = normalizeToken(term);
    if (!t) continue;
    if (normalizedText.includes(t)) return term;
  }
  return null;
}

export type WriteInPolicy = {
  allowWriteIn: boolean;
  writeInMaxLength: number;
  writeInBlocklist: string[];
  writeInProfanityFilter: boolean;
};

export type WriteInValidationResult =
  | { ok: true }
  | {
      ok: false;
      code: 'WRITE_IN_DISABLED' | 'WRITE_IN_TOO_LONG' | 'WRITE_IN_BLOCKED';
      message: string;
    };

export function validateWriteInText(
  option: string,
  policy: WriteInPolicy,
): WriteInValidationResult {
  if (!policy.allowWriteIn) {
    return {
      ok: false,
      code: 'WRITE_IN_DISABLED',
      message: 'Write-in options are disabled for this poll.',
    };
  }
  if (option.length > policy.writeInMaxLength) {
    return {
      ok: false,
      code: 'WRITE_IN_TOO_LONG',
      message: `Write-in option exceeds max length (${policy.writeInMaxLength}).`,
    };
  }
  const blockTerms = [
    ...policy.writeInBlocklist,
    ...(policy.writeInProfanityFilter ? DEFAULT_PROFANITY_TERMS : []),
  ];
  const blocked = containsBlockedToken(option, blockTerms);
  if (blocked) {
    return {
      ok: false,
      code: 'WRITE_IN_BLOCKED',
      message: 'Write-in option contains blocked language.',
    };
  }
  return { ok: true };
}
