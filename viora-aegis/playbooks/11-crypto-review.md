# Playbook 11 - CRYPTO review

**Goal:** decide whether the cryptography in this code is safe. Most crypto bugs
are not broken maths - they are a library used wrongly.

```bash
python3 scripts/viora.py plan crypto
```

---

## Law 7 first

> **Crypto is a library call.**

If the code implements a primitive - a cipher, a hash, a MAC, a key exchange, a
signature - that is the finding, before you analyse anything else. Report it and
recommend the platform library. Hand-rolled crypto that looks correct is still a
finding, because correctness here is not reviewable by inspection.

---

## Steps

1. **Find every crypto call site.**
   ```bash
   python3 scripts/viora.py scan --only CRYPTO
   ```
   Plus a manual sweep for: `hashlib`, `crypto`, `Cipher`, `AES`, `RSA`, `hmac`,
   `jwt`, `bcrypt`, `argon2`, `random`, `uuid`, `token`, `sign`, `verify`,
   `encrypt`, `decrypt`, `derive`.

2. **Classify each site by purpose before judging it.** The same primitive is
   fine in one role and a critical finding in another - this step prevents the
   most common false positive in the mode:

   | Purpose | Correct choice | Wrong is |
   |---|---|---|
   | Password storage | Argon2id, scrypt, bcrypt | any plain hash, even SHA-256 -> critical |
   | Token / ID generation | a CSPRNG (`secrets`, `crypto.randomBytes`) | `random`, `Math.random`, timestamp, counter -> high |
   | Integrity of untrusted data | HMAC with a secret key | a bare hash -> high |
   | Encryption at rest / in transit | AES-GCM, ChaCha20-Poly1305, libsodium | ECB, CBC without a MAC, DES, RC4 -> high |
   | Signature verification | the library's `verify`, algorithm pinned | `alg: none`, algorithm taken from the token -> critical |
   | Non-security digest (cache key, ETag, dedup) | anything, MD5 included | **not a finding** - read the usage first |

3. **Check the classic misuses.** Each is its own pass:
   - **Static IV or nonce.** A fixed IV with CTR/GCM is catastrophic - reusing a
     nonce with the same key destroys confidentiality and can leak the auth key.
   - **Static or missing salt** in password hashing, or a salt derived from the
     username.
   - **ECB mode** anywhere.
   - **CBC with no MAC** - malleable, and a padding oracle if errors differ.
   - **Encrypt without authenticate.** Prefer AEAD.
   - **Key from a password with no KDF**, or a key that is a string literal.
   - **Key and IV from the same source**, or an IV reused across messages.
   - **Cert verification disabled**: `verify=False`,
     `rejectUnauthorized: false`, `InsecureSkipVerify: true`, a custom trust-all
     callback.
   - **JWT**: is the algorithm pinned by the verifier? Is `alg` read from the
     token? Is `none` accepted? Are `exp`, `aud` and `iss` checked? Is an HMAC
     verifier reachable with an RSA public key as the secret?
   - **Key material in logs, errors or URLs.**

4. **Check comparison timing.** Any comparison of a secret, token, MAC, signature
   or password hash must be constant-time:
   - Python: `hmac.compare_digest`
   - Node: `crypto.timingSafeEqual`
   - Go: `subtle.ConstantTimeCompare`

   `==` on a MAC is a real finding. Judge severity by whether an attacker can
   measure it - remote over a noisy network is harder than local or same-datacentre,
   but a byte-by-byte early-return comparison is exploitable far more often than
   people assume. Report it; let the severity reflect reachability.

5. **Look for early returns in secret-dependent code.** A loop that breaks on the
   first mismatched byte leaks the position of the mismatch. So does a branch on
   a secret value, or a table lookup indexed by a secret.

6. **Check key lifecycle.** Where is the key generated, stored, rotated,
   destroyed? A key in the repo is Law 5. A key that cannot be rotated is a
   finding of its own.

7. **Check that secrets are cleared** where the language allows it. In
   languages with manual memory or long-lived buffers, key material should be
   zeroed after use rather than left for a heap dump or a core file. In managed
   languages, prefer a type designed for this (`SecretBox`, `bytearray` you can
   overwrite) over an immutable `String` you cannot. Note it as low or medium
   depending on the exposure - never claim a managed language can guarantee it.

8. **Verify with the gate**, then report. For crypto, the impact sentence must
   name what breaks: forgery, decryption, replay, key recovery, token prediction.

---

## Property-based testing for crypto fixes

Example-based tests miss crypto bugs, because the bug is usually at an edge you
did not think of. When you fix crypto, leave a property test:

| Property | Assertion |
|---|---|
| Round-trip | `decrypt(encrypt(m, k), k) == m` for all `m`, including empty and very long |
| Tamper detection | flipping any single bit of the ciphertext or tag makes decryption **fail**, not return garbage |
| Nonce uniqueness | `N` encryptions produce `N` distinct nonces |
| Wrong key fails | `decrypt(c, k2)` raises, for `k2 != k` |
| No length leak | error type and message are identical for a bad tag and bad padding |
| Determinism where required | a signature verifies across process restarts |

Generate inputs randomly, run many iterations, and include the boundary cases:
empty, one byte, exactly one block, one byte over a block, maximum size.

---

## Hard stops

- Do not "improve" a crypto implementation you were not asked to change. Ask
  first - a wrong crypto change is worse than the original bug, because it looks
  fixed.
- Do not report MD5 or SHA1 as critical without reading what the digest is for.
- Do not recommend a specific algorithm without checking what the platform
  already provides and what the rest of the codebase uses.
- Never generate or store a real key as an example in the repo.
