# 13 - Cryptographic code: timing, memory and property tests

Most security review asks "can the attacker send bad data?". Cryptographic code
asks two further questions that ordinary review never raises:

- **Does the code leak through *how long* it takes, or through what it touches?**
- **Does the secret still exist in memory after it was used?**

Neither has a signature a line scanner can catch reliably, so this is a reading
discipline, not a grep. Reach for it when the target implements or wraps
cryptography, handles keys or tokens, or compares secrets.

This reference backs `plan crypto` and `playbooks/11-crypto-review.md`.

---

## Law 7 first

> **Crypto is a library call.** If the code implements a primitive, that is the
> finding.

Before any timing analysis, ask whether this code should exist at all. Hand-built
AES, a bespoke MAC, custom padding, a homemade KDF, RSA assembled from a bignum
library - the correct fix is almost always "use libsodium, `cryptography`, Tink,
WebCrypto, or the platform primitive", not "make the loop constant-time".

Only when the implementation is genuinely necessary - a library, an embedded
target, a protocol with no available implementation - do the rest of this file
apply.

---

## 1. Constant-time comparison

Any comparison of a secret against attacker-supplied data must take the same time
regardless of how many bytes match. Ordinary equality short-circuits on the first
difference, which turns a 32-byte MAC into 32 sequential single-byte guesses.

### What must be constant-time

| Value | Why |
|---|---|
| MAC and signature verification | Byte-at-a-time forgery |
| Session tokens, API keys, reset tokens | Token recovery |
| Password hashes | Use the library's own verify function |
| HMAC-based webhook signatures | Very common real-world instance |
| OTP and TOTP codes | Small space, cheap to walk |

### The safe forms

| Language | Use |
|---|---|
| Python | `hmac.compare_digest(a, b)` |
| Node.js | `crypto.timingSafeEqual(a, b)` - equal lengths required |
| Go | `subtle.ConstantTimeCompare(a, b)` |
| Rust | the `subtle` crate: `ConstantTimeEq` |
| Java | `MessageDigest.isEqual(a, b)` |
| C | `sodium_memcmp`, or `CRYPTO_memcmp` |

### What to flag while reading

- `==`, `!=`, `equals`, `strcmp`, `memcmp` where one side is a secret
- A loop that `break`s or `return`s early on mismatch
- A length check that returns before the comparison, leaking the length
- Comparing **hex or base64 strings** rather than bytes - still short-circuits
- A "fast path" added for performance in front of a constant-time function

### Beyond comparison

Timing leaks are not only comparisons. While reading, flag:

- **Secret-dependent branches**: `if (key_bit)` choosing between code paths
- **Secret-dependent indexing**: `table[secret_byte]` - a cache-timing oracle
- **Secret-dependent loop bounds**: iterations proportional to key or scalar bits
- **Early exit on padding or format errors** - the classic padding oracle
- **Error messages that distinguish failure causes**: "bad padding" versus "bad
  MAC" is an oracle even at constant time

Decrypt-then-verify is the wrong order. Verify the MAC first, in constant time,
then decrypt; or use an AEAD mode and stop hand-assembling this.

---

## 2. Zeroization - the secret's lifetime

A key that is no longer needed but still resident can reach a core dump, a crash
report, swap, a hibernation file, a container snapshot, or another process
reading freed memory.

### What to check

1. **Is the secret wiped after use?** Not set to `null` or reassigned - actually
   overwritten.
2. **Is the wipe guaranteed on the error path?** A `return` inside a `catch`
   that skips the cleanup is the usual bug (Law 4 applies to cleanup too).
3. **How many copies exist?** Every copy needs wiping, and copies appear
   invisibly: string concatenation, string formatting, logging, JSON
   serialisation, a growing buffer that reallocates, an immutable type.
4. **Can the compiler remove the wipe?** A plain memory-set to zero on a buffer
   that is never read again is dead-store-eliminable. Use a primitive the
   compiler is not allowed to drop.

### The safe forms

| Language | Use | Note |
|---|---|---|
| Rust | `zeroize` crate, `Zeroizing<T>`, `ZeroizeOnDrop` | Idiomatic and reliable |
| C | `explicit_bzero`, `memset_s`, `SecureZeroMemory`, `sodium_memzero` | Never plain `memset` |
| Go | overwrite the byte slice; keep secrets out of `string` | `string` is immutable - it cannot be wiped |
| Python | `bytearray` and overwrite in place | `bytes` and `str` are immutable; treat wiping as best-effort |
| Java | `char[]` and `Arrays.fill`, not `String` | `String` lives in the pool |
| Node.js | `buf.fill(0)` | Avoid strings for key material |

**Be honest about the ceiling.** In garbage-collected, immutable-string languages
you cannot guarantee erasure. The correct report says so and recommends limiting
lifetime and copies rather than promising a wipe that does not happen. Do not
report "secret zeroized" when the language cannot deliver it.

---

## 3. Property-based testing for crypto

Example-based tests confirm the cases the author thought of, which is exactly the
wrong shape for cryptographic code. Properties are stated once and checked
against thousands of generated inputs, including the empty and maximal ones the
author did not consider.

### Properties worth stating

| Property | Statement |
|---|---|
| Round trip | `decrypt(encrypt(m, k), k) == m` for all `m` |
| Wrong key fails | `decrypt(c, k2)` fails cleanly, never returns garbage plaintext |
| Tamper detection | Flipping any single bit of the ciphertext, nonce or tag makes verification fail |
| Determinism or not | A deterministic scheme always matches; a randomised one never repeats a ciphertext for the same input |
| No nonce reuse | Across many encryptions, all nonces are distinct |
| Verify accepts only valid | A signature verifies under its own key and fails under any other |
| Length and boundaries | Empty input, one byte, exactly one block, block-plus-one, very large |
| Known-answer vectors | Official test vectors still pass - this is where property tests need help |

### Tools

| Language | Tool |
|---|---|
| Python | Hypothesis |
| Rust | proptest, quickcheck |
| Go | native fuzzing, `testing/quick` |
| JavaScript | fast-check |
| Java | jqwik |
| C and C++ | libFuzzer or AFL++ for parsers and decoders |

A tamper-detection property is the single highest-value test to add, because it
catches the whole family of "verification was never actually wired up" bugs -
including a verify function whose result is computed and then ignored.

---

## 4. Other frequent findings in crypto code

| Finding | Why it matters |
|---|---|
| Randomness from a non-CSPRNG (`math/rand`, `random`, `Math.random`, `rand()`) | Predictable keys, nonces, tokens |
| Nonce or IV reused, or a counter that resets | Catastrophic for CTR, GCM, ChaCha20 |
| ECB mode, or an unauthenticated CBC | Structure leaks; malleable ciphertext |
| Fast hash for passwords (MD5, SHA-1, single SHA-256) | Use Argon2id, scrypt or bcrypt |
| Low KDF iteration counts | Read the actual number, not the flag name |
| Signature verification result computed but unused | Verification that never fails |
| Algorithm chosen by the attacker-supplied header (`alg: none`) | JWT confusion |
| Keys committed to the repository (Law 5) | Rotate; do not just delete |
| No key rotation or versioning path | You cannot recover from a compromise |

---

## 5. How to report this class honestly

Timing findings are frequently dismissed as theoretical, so structure them so
that they cannot be:

1. **Name the oracle.** What observable differs, and with what input.
2. **Name the attacker's position.** Same host, same network, or remote. Remote
   timing attacks over a network are practical, but say which case you mean.
3. **State the work factor.** Byte-at-a-time recovery of a 32-byte MAC is
   roughly 32 times 256 attempts, not 2 to the 256.
4. **Give the one-line fix.** Name the exact function for this language.
5. **Give the verification.** A test that fails before the fix and passes after,
   or the constant-time function's own presence in the diff.
6. **Say what you did not measure.** You did not benchmark it, so do not claim a
   measured leak. `LIKELY` with a named oracle is an honest and useful verdict.

---

## Attribution

The three focus areas of this reference - constant-time analysis, zeroization
audit, and property-based testing as the right shape of test for cryptographic
code - follow the specialised review methodology published by
[Trail of Bits](https://github.com/trailofbits/skills), licensed CC-BY-SA-4.0.
**No text has been reproduced**: the methodology is restated here in our own
words, with our own language tables and reporting rules, so that this pack can
remain MIT-licensed. Their originals go considerably deeper on each topic and are
worth reading directly for any real cryptographic engagement.
