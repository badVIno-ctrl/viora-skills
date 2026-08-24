# Language and framework playbooks

Per-language footguns and the safe API to replace them. Jump to your stack; ignore the rest.

---

## JavaScript / TypeScript (Node)

| Dangerous | Safe |
|---|---|
| `` db.query(`SELECT * FROM u WHERE id=${id}`) `` | `db.query('SELECT * FROM u WHERE id=$1', [id])` |
| `child_process.exec(cmd)` | `execFile('git', ['log', ref])` |
| `eval`, `new Function`, `setTimeout("code")` | Lookup table / parser |
| `el.innerHTML = data` | `el.textContent = data`, or `DOMPurify.sanitize()` |
| `JSON.parse` on unvalidated input | Zod / Valibot schema `.parse()` |
| `require(userPath)` / dynamic `import(userPath)` | Static import map |
| `Object.assign(user, req.body)` | Explicit field allowlist (mass assignment → `isAdmin`) |
| `crypto.createHash('md5')` for passwords | `argon2.hash()` or `bcrypt` cost ≥ 12 |
| `Math.random()` for tokens | `crypto.randomBytes(32).toString('base64url')` |
| `a === b` for secrets | `crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b))` |
| `express.json()` | `express.json({ limit: '100kb' })` |

**Express baseline:** `helmet()` · `cors({ origin: ALLOWLIST, credentials: true })` ·
`express-rate-limit` on auth routes · `cookie-session`/`express-session` with
`{ httpOnly: true, secure: true, sameSite: 'lax' }` · a central error handler that returns a generic
message plus a correlation ID · validation middleware on every route.

**Prototype pollution:** never merge untrusted objects recursively. Reject keys `__proto__`,
`constructor`, `prototype`; prefer `Object.create(null)` for maps; use `structuredClone`.

**Next.js / React:** anything in a Server Component or route handler runs on the server — check
authorization there, not in the page. `NEXT_PUBLIC_*` is public: never a secret. Server Actions are
public endpoints — validate input and authorize inside them. Middleware alone is not authorization
(it can be bypassed on some deployment topologies).

**npm hygiene:** `npm ci` · `--ignore-scripts` by default · `npm audit --omit=dev` · review any
dependency that adds a `postinstall`.

---

## Python

| Dangerous | Safe |
|---|---|
| `cursor.execute(f"... {x}")` | `cursor.execute("... %s", (x,))` — driver params, not `%` |
| `os.system`, `subprocess(..., shell=True)` | `subprocess.run(["git", "log", ref], shell=False)` |
| `pickle.loads`, `dill`, `marshal` | `json`, or msgpack + schema |
| `yaml.load(data)` | `yaml.safe_load(data)` |
| `eval`, `exec` | `ast.literal_eval` or a real parser |
| `xml.etree` on untrusted XML | `defusedxml` |
| `random.*` for tokens | `secrets.token_urlsafe(32)` |
| `hashlib.md5(pw)` | `argon2-cffi` / `bcrypt` |
| `requests.get(url, verify=False)` | Fix the CA bundle; never disable verify |
| `tarfile.extractall()` | `filter="data"` (3.12+) or validate every member path |
| `torch.load(path)` | `torch.load(path, weights_only=True)` / safetensors |
| `assert user.is_admin` | Real check — `assert` vanishes under `python -O` |

**Django:** keep `DEBUG=False` and a real `ALLOWED_HOSTS` · use the ORM; `.raw()`/`.extra()` need
params · never remove `{% csrf_token %}` or add `@csrf_exempt` without a written reason · use
`get_object_or_404(Model, pk=pk, owner=request.user)` — the ownership predicate belongs *in* the
query · `SECURE_*` settings on · `django-csp`.

**Flask/FastAPI:** validate with Pydantic; `response_model` to filter output fields · never
`render_template_string` with user data · FastAPI dependencies for authz, applied at the router ·
set `allow_origins` explicitly — `["*"]` with credentials is rejected by browsers *and* wrong.

---

## PHP

| Dangerous | Safe |
|---|---|
| `mysqli_query("... $id")` | PDO prepared statements with bound params |
| `unserialize($input)` | `json_decode($input, true)` |
| `include $_GET['page']` | Allowlist map of page → file |
| `shell_exec`, `system`, backticks | `escapeshellarg` at minimum; better, avoid |
| `extract($_POST)` | Explicit assignment |
| `md5($password)` | `password_hash($pw, PASSWORD_ARGON2ID)` |
| `==` on hashes | `hash_equals()` |
| `move_uploaded_file` with client name | Random name, MIME by magic bytes, outside web root |

**Laravel:** Eloquent by default; `DB::raw` needs bindings · `$fillable`, never `$guarded = []` ·
policies + `authorize()` on every action · `{{ }}` escapes, `{!! !!}` does not · keep `APP_DEBUG=false`.

---

## Java / Kotlin

- `PreparedStatement` always; never concatenate into `Statement`.
- `ProcessBuilder` with an argument list; never `Runtime.exec(String)`.
- Never `ObjectInputStream.readObject()` on untrusted bytes — that is RCE by design.
- XML: `setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)`.
- `SecureRandom`, not `Random`. `MessageDigest.isEqual` for secret comparison.
- Spring Security: prefer `@PreAuthorize` with an ownership expression over URL patterns; verify the
  filter chain order; `permitAll()` on `/**` is a finding.
- Deserialization gadgets ride on Jackson `enableDefaultTyping` and SnakeYAML defaults — disable both.
- Log4Shell class of bug: never log user input through a format-capable logger without escaping.

---

## C# / .NET

- Parameterised `SqlCommand` or EF Core LINQ; `FromSqlRaw` requires parameters.
- Never `BinaryFormatter` (removed for a reason). Use `System.Text.Json`.
- `XmlReaderSettings { DtdProcessing = DtdProcessing.Prohibit, XmlResolver = null }`.
- `RandomNumberGenerator`, not `Random`. `CryptographicOperations.FixedTimeEquals`.
- `[Authorize]` by default via a global filter; `[AllowAnonymous]` is the exception you justify.
- ASP.NET Core: antiforgery tokens on state-changing forms; `Html.Raw` is a bypass.

---

## Go

- `db.Query("... WHERE id = $1", id)` — `fmt.Sprintf` into SQL is the classic Go SQLi.
- `exec.Command("git", "log", ref)` — never `exec.Command("sh", "-c", cmd)`.
- `crypto/rand`, not `math/rand`. `subtle.ConstantTimeCompare` for secrets.
- `tls.Config{InsecureSkipVerify: true}` is a critical finding, in tests too.
- **Check every error.** `_ = err` on an auth or crypto call is a fail-open bug.
- `html/template` (auto-escaping), never `text/template`, for HTML.
- Set `http.Server` timeouts (`ReadHeaderTimeout`, `ReadTimeout`, `WriteTimeout`) — defaults are none.
- Integer overflow on 32-bit conversions in size/length arithmetic.

---

## Ruby / Rails

- `where("name = ?", name)`; never `where("name = '#{name}'")`.
- `Marshal.load` and `YAML.load` on untrusted input → RCE. Use `YAML.safe_load`.
- Strong parameters: `params.require(:user).permit(:email)` — mass assignment is the Rails classic.
- `html_safe` and `raw` disable escaping; `sanitize` is the safe helper.
- Never `skip_before_action :verify_authenticity_token` without a documented reason.
- Pundit/CanCanCan policies, verified with `verify_authorized`.

---

## Rust

- Memory safety is not application safety: SQLi, SSRF, authz bugs and path traversal all apply.
- Audit every `unsafe` block; justify it in a comment.
- `sqlx` compile-time-checked queries or bound parameters.
- `cargo audit` / `cargo deny` in CI.
- Beware `.unwrap()` on user-controlled input — a panic in a request handler is a DoS.

---

## C / C++

- Bounds: `snprintf`/`strlcpy` over `sprintf`/`strcpy`; check every length calculation for overflow.
- Free once, null after; prefer RAII / smart pointers; watch use-after-free on error paths.
- Never `system()` or `popen()` with constructed strings; use `execve` with an argv array.
- Format strings must be literals — `printf(user)` is arbitrary read/write.
- Compile with `-D_FORTIFY_SOURCE=2 -fstack-protector-strong -Wformat-security`, ASAN/UBSAN in CI.

---

## SQL layer (any language)

- Application DB user: no `DROP`, no `CREATE`, no superuser, no access to other schemas.
- Row-level security when the database supports it — it survives an ORM mistake.
- Never build identifiers (table/column names) from user input; map them through an allowlist.
- `LIKE` with user input needs escaping of `%` and `_`; cap the pattern length (DoS).
- Migrations reviewed like code; a migration can drop a constraint that was a control.

---

## Shell scripts

- `set -euo pipefail` at the top of every script.
- Quote every expansion: `"$var"`, `"$@"`. Unquoted expansion is word-splitting *and* globbing.
- Never `eval`; never `curl | bash` — download, verify a checksum, then run.
- `mktemp -d` for temporary files; never a predictable `/tmp/name` (symlink attacks).
- Validate arguments with a case allowlist before using them in a path or command.

---

## Terraform / Kubernetes / IaC

- No `0.0.0.0/0` ingress except 80/443 on a load balancer; never on SSH/RDP/database ports.
- Buckets: block public access, enforce encryption, enable versioning and access logging.
- Secrets via a secret manager, never in `.tf`, `.tfvars`, ConfigMaps or environment blocks in git.
- Pods: `runAsNonRoot: true`, `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`,
  drop all capabilities, resource limits set, NetworkPolicy default-deny.
- Remote state encrypted with locking and restricted access — state files contain secrets.
- Pin provider and module versions; run `checkov`/`tfsec` in CI.
