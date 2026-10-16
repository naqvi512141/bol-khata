/**
 * Pure ULID generator (Universally Unique Lexicographically Sortable Identifier).
 * 26 characters: 10 chars for 48-bit UNIX timestamp (ms) + 16 chars for 80-bit randomness.
 * Crockford's Base32 character set (excludes I, L, O, U to avoid confusion).
 */

const ENCODING = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
const ENCODING_LEN = ENCODING.length;

export function generateUlid(now: number = Date.now()): string {
  // 10 chars timestamp (48-bit)
  let timeStr = '';
  let time = Math.floor(now);
  for (let i = 9; i >= 0; i--) {
    const mod = time % ENCODING_LEN;
    timeStr = ENCODING.charAt(mod) + timeStr;
    time = Math.floor(time / ENCODING_LEN);
  }

  // 16 chars randomness (80-bit)
  let randStr = '';
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    const buffer = new Uint8Array(16);
    crypto.getRandomValues(buffer);
    for (let i = 0; i < 16; i++) {
      randStr += ENCODING.charAt(buffer[i] % ENCODING_LEN);
    }
  } else {
    for (let i = 0; i < 16; i++) {
      const randInt = Math.floor(Math.random() * ENCODING_LEN);
      randStr += ENCODING.charAt(randInt);
    }
  }

  return timeStr + randStr;
}
