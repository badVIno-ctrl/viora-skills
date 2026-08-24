# Secure patterns — copy-ready

Implementations to paste and adapt while writing the fix. Every snippet assumes input arrives
untrusted and enforcement happens server-side.

---

## 1. Input validation at the boundary

```ts
// TypeScript — Zod. Validate, coerce, and strip unknown keys in one place.
import { z } from "zod";

const CreateOrder = z.object({
  productId: z.string().uuid(),
  quantity:  z.number().int().min(1).max(100),
  note:      z.string().max(500).optional(),
}).strict();                      // .strict() blocks mass assignment

export async function createOrder(req, res) {
  const parsed = CreateOrder.safeParse(req.body);
  if (!parsed.success) return res.status(400).json({ error: "Invalid request" });
  // price is NEVER taken from the client
  const price = await catalog.priceOf(parsed.data.productId);
  ...
}
```

```python
# Python — Pydantic v2
from pydantic import BaseModel, Field, ConfigDict

class CreateOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")   # blocks mass assignment
    product_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    quantity:   int = Field(ge=1, le=100)
```

**Rule:** allowlist the shape, reject unknown fields, cap every length and number, and never accept a
price, role, tenant or status from the client.

---

## 2. Authorization that cannot be forgotten

```ts
// Bad: authentication only. Any logged-in user reads any invoice.
const invoice = await db.invoice.findUnique({ where: { id: req.params.id } });

// Good: ownership is part of the query, so it cannot be skipped.
const invoice = await db.invoice.findFirst({
  where: { id: req.params.id, tenantId: req.session.tenantId },
});
if (!invoice) return res.status(404).end();   // 404, not 403 — no existence oracle
```

```python
# Django — ownership in the lookup, not after it
obj = get_object_or_404(Invoice, pk=pk, owner=request.user)
```

```ts
// Central policy, applied by the router — not copy-pasted per handler
router.use(requireAuth);
router.get("/invoices/:id", authorize("invoice:read"), handler);
```

For multi-tenant systems, wrap the data layer so a query without a tenant predicate is impossible:
a scoped repository, an ORM global scope, or Postgres row-level security.

---

## 3. Passwords and sessions

```ts
import argon2 from "argon2";
const hash = await argon2.hash(password, { type: argon2.argon2id });
const ok   = await argon2.verify(hash, password);   // constant-time inside

// On successful login: rotate the session id (prevents fixation)
req.session.regenerate(() => { req.session.userId = user.id; });
```

```ts
app.use(session({
  cookie: { httpOnly: true, secure: true, sameSite: "lax", maxAge: 12 * 3600_000 },
  rolling: true, resave: false, saveUninitialized: false,
}));
```

Uniform failure response for both "no such user" and "wrong password", with comparable timing.
Rate-limit before you hash — Argon2 is expensive, and that is a DoS vector.

---

## 4. Rate limiting

```ts
import rateLimit from "express-rate-limit";

const authLimiter = rateLimit({
  windowMs: 15 * 60_000,
  limit: 8,
  standardHeaders: true,
  keyGenerator: (req) => `${req.ip}:${String(req.body?.email ?? "").toLowerCase()}`,
  message: { error: "Too many attempts. Try again later." },
});

app.post("/login",           authLimiter, login);
app.post("/password/reset",  authLimiter, reset);
app.post("/register",        authLimiter, register);
```

Limit by IP **and** account so one attacker cannot lock out a user, and one user cannot be attacked
from many IPs. Add exponential backoff and a CAPTCHA after repeated failures.

---

## 5. SSRF guard

```python
import ipaddress, socket
from urllib.parse import urlparse

ALLOWED_HOSTS = {"api.partner.com", "cdn.partner.com"}

def safe_fetch(raw_url: str, timeout: float = 5.0):
    u = urlparse(raw_url)
    if u.scheme not in ("https",):            # no http, file, gopher, ftp, data
        raise ValueError("scheme not allowed")
    if u.hostname not in ALLOWED_HOSTS:       # allowlist beats any denylist
        raise ValueError("host not allowed")

    # Resolve once, validate, then connect to THAT ip (closes the DNS-rebinding TOCTOU window)
    infos = socket.getaddrinfo(u.hostname, u.port or 443, proto=socket.IPPROTO_TCP)
    ips = {ipaddress.ip_address(i[4][0]) for i in infos}
    for ip in ips:
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("target resolves to a non-public address")

    # requests does not let you pin the IP; use an adapter that connects to `ips`,
    # or run the call through an egress proxy that enforces the same allowlist.
    return http_client.get(raw_url, timeout=timeout, allow_redirects=False)
```

**Non-negotiable:** allowlist hosts · HTTPS only · block redirects (or re-validate each hop) ·
explicit timeout · block `169.254.169.254` and all private ranges · cap the response size.
In production the strongest control is a **network egress allowlist**, not application code.

---

## 6. Path traversal / uploads

```python
import os, secrets

UPLOAD_ROOT = os.path.realpath("/srv/uploads")

def safe_path(user_filename: str) -> str:
    name = os.path.basename(user_filename)              # strip directories
    target = os.path.realpath(os.path.join(UPLOAD_ROOT, name))
    if not target.startswith(UPLOAD_ROOT + os.sep):     # confine to the root
        raise ValueError("path escapes upload root")
    return target

def store(upload) -> str:
    if upload.size > 5 * 1024 * 1024:
        raise ValueError("too large")
    head = upload.stream.read(512); upload.stream.seek(0)
    if not head.startswith((b"\x89PNG", b"\xff\xd8\xff")):   # magic bytes, not the extension
        raise ValueError("unsupported type")
    stored = secrets.token_urlsafe(16) + ".bin"        # never trust the client's name
    ...
```

Serve uploads from a separate domain or via a handler that forces
`Content-Disposition: attachment` and `X-Content-Type-Options: nosniff`. Never let an upload
directory execute code.

**Archives:** validate every entry's resolved path, cap entry count and total uncompressed size
(zip bombs), and refuse symlinks. Python 3.12+: `extractall(path, filter="data")`.

---

## 7. Security headers

```ts
import helmet from "helmet";

app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc:  ["'self'", (req, res) => `'nonce-${res.locals.nonce}'`],
      styleSrc:   ["'self'"],
      imgSrc:     ["'self'", "data:", "https://cdn.example.com"],
      connectSrc: ["'self'", "https://api.example.com"],
      objectSrc:  ["'none'"],
      frameAncestors: ["'none'"],
      baseUri:    ["'self'"],
      formAction: ["'self'"],
      upgradeInsecureRequests: [],
    },
  },
  hsts: { maxAge: 31_536_000, includeSubDomains: true, preload: true },
  referrerPolicy: { policy: "strict-origin-when-cross-origin" },
}));
```

Use a per-request nonce for inline scripts. `unsafe-inline` and `unsafe-eval` defeat the point of a
CSP. Verify with `viora headers https://your-site`.

---

## 8. CORS

```ts
const ALLOWED = new Set(["https://app.example.com", "https://admin.example.com"]);

app.use(cors({
  origin(origin, cb) {
    if (!origin) return cb(null, false);          // same-origin / server-to-server
    cb(null, ALLOWED.has(origin));                // compare, never echo
  },
  credentials: true,
  methods: ["GET", "POST", "PATCH", "DELETE"],
  maxAge: 600,
}));
```

Never reflect `req.headers.origin`. Never combine `*` with credentials. Subdomain wildcards are a
takeover risk — one forgotten staging subdomain reads production data.

---

## 9. Webhooks

```ts
import crypto from "crypto";

export function verifyWebhook(rawBody: Buffer, signature: string, timestamp: string) {
  const age = Math.abs(Date.now() / 1000 - Number(timestamp));
  if (!Number.isFinite(age) || age > 300) throw new Error("stale");   // replay window

  const expected = crypto.createHmac("sha256", process.env.WEBHOOK_SECRET!)
                         .update(`${timestamp}.`).update(rawBody).digest();
  const got = Buffer.from(signature, "hex");
  if (got.length !== expected.length || !crypto.timingSafeEqual(got, expected))
    throw new Error("bad signature");
}
```

Verify against the **raw** body, before any JSON parsing or middleware rewriting. Make the handler
idempotent by event ID — providers retry, and attackers replay.

---

## 10. Secrets

```ts
// Fail fast. A default value means the app ships with a shared, public credential.
function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required environment variable: ${name}`);
  return v;
}
export const JWT_SECRET = requireEnv("JWT_SECRET");
```

Rotation-ready design: read the secret through one accessor, support two valid keys during rotation
(verify with old and new, sign with new), and log key IDs, never key material.

---

## 11. Error handling that fails closed

```ts
app.use((err, req, res, _next) => {
  const correlationId = crypto.randomUUID();
  logger.error({ correlationId, err, path: req.path, userId: req.session?.userId });
  res.status(err.status ?? 500).json({
    error: "Something went wrong",   // never err.message, never a stack trace
    correlationId,                   // the user quotes this to support
  });
});
```

```python
# Law 4: an exception in a security decision means DENY.
def can_access(user, resource) -> bool:
    try:
        return policy.check(user, resource)
    except Exception:
        logger.exception("authz check failed", extra={"user": user.id})
        return False        # never True
```

---

## 12. Logging

```ts
const REDACT = /("?(password|passwd|secret|token|api[_-]?key|authorization|cvv|ssn)"?\s*[:=]\s*)("[^"]*"|\S+)/gi;
const safe = (s: string) => s.replace(REDACT, '$1"[REDACTED]"');

logger.info({
  event: "auth.login.failed",
  userId: user?.id ?? null,      // an id, never an email or a password
  ip: req.ip,
  correlationId,
});
```

Log these, always: login success/failure, logout, password and MFA changes, authorization denials,
privilege changes, admin actions, payment events, data exports. Alert on rate anomalies.

---

## 13. Output encoding cheat sheet

| Context | Encode with | Never |
|---|---|---|
| HTML body | Template auto-escaping / `textContent` | `innerHTML` with data |
| HTML attribute | Attribute-encode; always quote | Unquoted attributes |
| JavaScript | `JSON.stringify` into a `<script type="application/json">` block | String interpolation into JS |
| URL / query | `encodeURIComponent` | Raw concatenation |
| CSS | Avoid dynamic CSS entirely | `style` built from input |
| SQL | Bound parameters | Any concatenation |
| Shell | argv array | Any concatenation |
| LDAP / XPath | Library escaping | Filter string building |
| Log line | Strip CR/LF, escape | Raw user text |

Encode **at the sink**, in the sink's context. Encoding early or twice creates its own bugs.
