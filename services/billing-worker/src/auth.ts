import type { Context, MiddlewareHandler } from 'hono';
import { HTTPException } from 'hono/http-exception';

export interface JWTPayload {
  sub: string; // user id
  email?: string;
  iat?: number;
  exp?: number;
}

export interface AuthEnv {
  JWT_SECRET: string;
}

const encoder = new TextEncoder();

function base64UrlDecode(input: string): Uint8Array {
  const pad = input.length % 4 === 0 ? '' : '='.repeat(4 - (input.length % 4));
  const b64 = (input + pad).replace(/-/g, '+').replace(/_/g, '/');
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function bytesToString(b: Uint8Array): string {
  return new TextDecoder().decode(b);
}

function constantTimeEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

/** Verify an HS256 JWT and return its payload, or throw. */
export async function verifyJwt(token: string, secret: string): Promise<JWTPayload> {
  const parts = token.split('.');
  if (parts.length !== 3) throw new HTTPException(401, { message: 'malformed token' });
  const [h, p, s] = parts;

  const header = JSON.parse(bytesToString(base64UrlDecode(h))) as { alg?: string; typ?: string };
  if (header.alg !== 'HS256') throw new HTTPException(401, { message: 'unsupported alg' });

  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign', 'verify']
  );

  const signingInput = encoder.encode(`${h}.${p}`);
  const expected = new Uint8Array(await crypto.subtle.sign('HMAC', key, signingInput));
  const provided = base64UrlDecode(s);
  if (!constantTimeEqual(expected, provided)) {
    throw new HTTPException(401, { message: 'invalid signature' });
  }

  const payload = JSON.parse(bytesToString(base64UrlDecode(p))) as JWTPayload;
  const now = Math.floor(Date.now() / 1000);
  if (payload.exp && now >= payload.exp) {
    throw new HTTPException(401, { message: 'token expired' });
  }
  if (!payload.sub) throw new HTTPException(401, { message: 'missing sub' });
  return payload;
}

export interface AuthVariables {
  user: JWTPayload;
}

export const requireAuth = (): MiddlewareHandler<{
  Bindings: AuthEnv;
  Variables: AuthVariables;
}> => async (c, next) => {
  const header = c.req.header('authorization') || c.req.header('Authorization');
  if (!header || !header.toLowerCase().startsWith('bearer ')) {
    throw new HTTPException(401, { message: 'missing bearer token' });
  }
  const token = header.slice(7).trim();
  const payload = await verifyJwt(token, c.env.JWT_SECRET);
  c.set('user', payload);
  await next();
};

/** Test-only helper: sign an HS256 JWT. Not exported through index. */
export async function signJwt(payload: JWTPayload, secret: string): Promise<string> {
  const header = { alg: 'HS256', typ: 'JWT' };
  const b64 = (b: Uint8Array | string) => {
    const bytes = typeof b === 'string' ? encoder.encode(b) : b;
    let s = '';
    for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
    return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
  };
  const h = b64(JSON.stringify(header));
  const p = b64(JSON.stringify(payload));
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const sig = new Uint8Array(await crypto.subtle.sign('HMAC', key, encoder.encode(`${h}.${p}`)));
  return `${h}.${p}.${b64(sig)}`;
}

export function _testing_constantTimeEqual(a: Uint8Array, b: Uint8Array) {
  return constantTimeEqual(a, b);
}
