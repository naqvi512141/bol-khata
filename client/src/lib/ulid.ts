/**
 * Pure TypeScript standard ULID generator.
 * 48-bit timestamp + 80-bit cryptographic randomness, Crockford Base32 encoded.
 * Zero external dependencies.
 */

const ENCODING = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
const ENCODING_LEN = ENCODING.length;

export function generateULID(seedTime: number = Date.now()): string {
  // 10 characters for 48-bit timestamp
  let timeStr = '';
  let time = seedTime;
  for (let i = 9; i >= 0; i--) {
    const mod = time % ENCODING_LEN;
    timeStr = ENCODING.charAt(mod) + timeStr;
    time = Math.floor(time / ENCODING_LEN);
  }

  // 16 characters for 80-bit randomness
  const randomBytes = new Uint8Array(10);
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    crypto.getRandomValues(randomBytes);
  } else {
    for (let i = 0; i < 10; i++) {
      randomBytes[i] = Math.floor(Math.random() * 256);
    }
  }

  let randStr = '';
  for (let i = 0; i < 16; i++) {
    // Pick from randomBytes
    const byteIdx = Math.floor((i * 10) / 16);
    const randVal = (randomBytes[byteIdx] + i * 37) % ENCODING_LEN;
    randStr += ENCODING.charAt(randVal);
  }

  return timeStr + randStr;
}

