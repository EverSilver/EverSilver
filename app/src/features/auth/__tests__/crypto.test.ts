/**
 * PBKDF2 password-hashing crypto helper.
 */
import { describe, expect, it } from 'vitest';

import { hashPassword, verifyPassword } from '../crypto';

describe('crypto', { timeout: 30_000 }, () => {
  it('produces a versioned PBKDF2-SHA256 hash with random salt', async () => {
    const a = await hashPassword('correct horse battery staple');
    expect(a.algo).toBe('pbkdf2-sha256');
    expect(a.iterations).toBe(600_000);
    expect(typeof a.salt).toBe('string');
    expect(typeof a.hash).toBe('string');

    // Different invocations of hashPassword produce different salts + hashes.
    const b = await hashPassword('correct horse battery staple');
    expect(b.salt).not.toBe(a.salt);
    expect(b.hash).not.toBe(a.hash);
  });

  it('verifies a correct password', async () => {
    const stored = await hashPassword('hunter2');
    expect(await verifyPassword('hunter2', stored)).toBe(true);
  });

  it('rejects an incorrect password', async () => {
    const stored = await hashPassword('hunter2');
    expect(await verifyPassword('hunter1', stored)).toBe(false);
    expect(await verifyPassword('', stored)).toBe(false);
    expect(await verifyPassword('HUNTER2', stored)).toBe(false);
  });

  it('rejects records with an unknown algorithm tag', async () => {
    const stored = await hashPassword('hunter2');
    const tampered = { ...stored, algo: 'not-a-real-algo' as 'pbkdf2-sha256' };
    expect(await verifyPassword('hunter2', tampered)).toBe(false);
  });
});
