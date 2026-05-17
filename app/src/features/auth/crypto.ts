/**
 * Password hashing helpers built on the WebCrypto SubtleCrypto API.
 *
 * Used by LocalAuthProvider so the on-disk credential store is not a
 * plaintext password file. PBKDF2 with 600k iterations matches OWASP 2023
 * guidance for SHA-256.
 */

const ITERATIONS = 600_000;
const KEY_LEN_BITS = 256;
const SALT_LEN = 16;

const enc = new TextEncoder();

function toBase64(bytes: Uint8Array): string {
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}

function fromBase64(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

/** Constant-time equality on equal-length byte arrays. */
function timingSafeEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

async function deriveKey(password: string, salt: Uint8Array): Promise<Uint8Array> {
  const baseKey = await crypto.subtle.importKey(
    'raw',
    enc.encode(password),
    { name: 'PBKDF2' },
    false,
    ['deriveBits']
  );
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', salt, iterations: ITERATIONS, hash: 'SHA-256' },
    baseKey,
    KEY_LEN_BITS
  );
  return new Uint8Array(bits);
}

export interface HashedPassword {
  /** Algorithm tag — versioned so we can migrate later. */
  algo: 'pbkdf2-sha256';
  iterations: number;
  /** Base64 salt. */
  salt: string;
  /** Base64 derived key. */
  hash: string;
}

export async function hashPassword(password: string): Promise<HashedPassword> {
  const salt = crypto.getRandomValues(new Uint8Array(SALT_LEN));
  const hash = await deriveKey(password, salt);
  return {
    algo: 'pbkdf2-sha256',
    iterations: ITERATIONS,
    salt: toBase64(salt),
    hash: toBase64(hash),
  };
}

export async function verifyPassword(password: string, stored: HashedPassword): Promise<boolean> {
  if (stored.algo !== 'pbkdf2-sha256') return false;
  const salt = fromBase64(stored.salt);
  const expected = fromBase64(stored.hash);
  const baseKey = await crypto.subtle.importKey(
    'raw',
    enc.encode(password),
    { name: 'PBKDF2' },
    false,
    ['deriveBits']
  );
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', salt, iterations: stored.iterations, hash: 'SHA-256' },
    baseKey,
    expected.length * 8
  );
  return timingSafeEqual(new Uint8Array(bits), expected);
}
