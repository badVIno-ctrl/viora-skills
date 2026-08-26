# 08 - Stack notes: the exact commands, per stack

This file exists so that no agent ever has to guess a command. Guessed commands are how
"I ran the tests" becomes a lie: `npm test` in a pnpm monorepo, `pytest` where there is no
pytest, `go test` from the wrong directory. All three exit non-zero and all three get
reported as "environment issue" instead of "I did not verify anything".

**Order of authority.** Never invent a command. Find it, in this order:

1. `bash scripts/verify.sh . --list` - detects and prints what this repo actually declares
2. CI config - `.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile`. **This is the
   ground truth.** It is what the team must pass to merge
3. `package.json` scripts / `Makefile` targets / `justfile` / `Taskfile.yml`
4. `CONTRIBUTING.md`, then `README.md`
5. Only now, the conventional defaults below

If steps 1-4 give nothing, say so in the report: *"this repository declares no gates I could
find; I verified by hand with X"*. That sentence is worth more than a green checkmark you
invented.

---

## Detect the stack in three commands

```bash
ls -a | head -40
cat package.json 2>/dev/null | head -40
ls .github/workflows/ 2>/dev/null && cat .github/workflows/*.yml 2>/dev/null | head -60
```

| Marker file | Stack | Go to |
|---|---|---|
| `package.json` | Node / TS / JS | [Node](#node--typescript) |
| `pnpm-lock.yaml` / `yarn.lock` / `bun.lockb` | Node, non-npm runner | [Runner](#pick-the-right-runner) |
| `turbo.json` / `nx.json` / `pnpm-workspace.yaml` / `lerna.json` | Monorepo | [Monorepo](#monorepos) |
| `next.config.*` / `vite.config.*` / `astro.config.*` | Frontend app | [Frontend](#frontend-specific) |
| `pyproject.toml` / `requirements.txt` / `setup.cfg` | Python | [Python](#python) |
| `go.mod` | Go | [Go](#go) |
| `Cargo.toml` | Rust | [Rust](#rust) |
| `*.xcodeproj` / `Package.swift` / `*.xcworkspace` | Swift / iOS | [Swift](#swift--ios) |
| `build.gradle(.kts)` / `settings.gradle` | Kotlin / Android / JVM | [Kotlin](#kotlin--android) |
| `composer.json` | PHP | [Other](#other-stacks-quick-table) |
| `Gemfile` | Ruby | [Other](#other-stacks-quick-table) |
| `*.csproj` / `*.sln` | .NET | [Other](#other-stacks-quick-table) |
| `Dockerfile` only | Container-only | Gates live in CI. Read the workflow file |
| none of the above | Unknown | Say UNPROVEN. Do not improvise |

---

## Node / TypeScript

### Pick the right runner

The lockfile decides. Using the wrong one either fails or, worse, silently installs a
different dependency tree.

| Lockfile | Run scripts with | Never |
|---|---|---|
| `package-lock.json` | `npm run <s>` | - |
| `pnpm-lock.yaml` | `pnpm run <s>` | `npm install` (rewrites the lockfile) |
| `yarn.lock` | `yarn <s>` | `npm run` |
| `bun.lockb` | `bun run <s>` | `npm run` |

### Gate pack

```bash
# read the declared scripts first - do not assume they exist
node -e "console.log(Object.keys(require('./package.json').scripts||{}).join('\n'))"

<runner> run format:check     # or prettier --check .
<runner> run lint             # eslint
<runner> run typecheck        # or: npx --no-install tsc --noEmit
<runner> run test
<runner> run build
```

**The one command that proves a change:** `npx --no-install tsc --noEmit`. It is fast, it
needs no test to exist, and it catches the single most common AI defect in a TS codebase - a
changed function signature with un-updated callers.

### Traps

- **`tsc --noEmit` is not `next build`.** Next.js, Vite and Remix do their own type handling
  and can fail after `tsc` passes. If a `build` script exists, run it.
- **`--no-install`** prevents `npx` from silently downloading a different TypeScript version.
- **A failing `postinstall` is not your bug.** Report it as an environment blocker; do not
  "fix" it by editing the lockfile.
- **Skipped tests are not passing tests.** `Tests: 3 passed, 41 skipped` is UNPROVEN.
  Report the skip count.
- **`any` is a silent gate bypass.** Adding `as any` or `@ts-expect-error` to make types pass
  is fabricated evidence. If you must, it goes in the report as a finding.
- **Vitest/Jest watch mode hangs CI.** Use `--run` (vitest) or `--ci --watchAll=false` (jest).

### Frontend specific

```bash
python3 scripts/ui_guard.py .          # margins, z-index, layout drift
<runner> run build                     # the only real check for a frontend change
```

A UI change with no screenshot and no build is UNPROVEN. Say so. "The component renders"
is not something you observed unless you observed it.

---

## Python

### Gate pack

```bash
ruff format --check .          # or: black --check .
ruff check .                   # or: flake8 .
mypy .                         # only if mypy.ini / [tool.mypy] exists
pytest -q                      # or: python3 -m unittest discover -q
python3 -m compileall -q .     # always available; proves syntax and nothing more
```

**The one command that proves a change:** `pytest -q` if a suite exists. If not,
`python3 -c "..."` exercising the exact function you changed, with the output pasted in.

### Traps

- **`python3 -m compileall` proves syntax only.** Never present it as "the tests pass".
  Its honest description is: *"the file parses"*.
- **Virtualenv.** If `.venv/` exists, use `.venv/bin/python3` and `.venv/bin/pytest`, or the
  imports will differ from the ones the project actually uses.
- **Mutable default arguments** (`def f(x, bucket=[])`) are the most common Python bug an
  agent both writes and fails to diagnose. See `evals/fixtures/f06-flaky-hypothesis`.
- **`unittest discover` needs an importable start directory.** Either add `tests/__init__.py`
  or use `-t .`; otherwise you get `ImportError: Start directory is not importable` and
  wrongly conclude the suite is broken.
- **Import-order side effects.** A test that passes alone and fails in the suite is shared
  state, not flakiness. Run both orders before forming a hypothesis.

---

## Go

### Gate pack

```bash
gofmt -l .                     # prints files needing formatting; empty output = clean
go vet ./...
go build ./...
go test ./...
go test -race ./...            # for anything touching goroutines or shared state
```

**The one command that proves a change:** `go build ./...` then `go test ./...`. Go's
compiler catches unused variables and imports, so a build failure is often the whole review.

### Traps

- **`./...` matters.** `go test` alone tests the current package only. An agent that runs
  `go test` in a subdirectory and reports "tests pass" has tested a fraction of the repo.
- **`gofmt -l .` succeeds (exit 0) while printing filenames.** Empty output is the pass
  condition, not the exit code. This is a real way to report a false PASS.
- **`-race` on concurrency changes is not optional.** Without it, the test proves the happy
  interleaving.
- **Error handling is the review.** `if err != nil { return err }` dropped or swallowed is
  the most common Go defect in generated code.

---

## Rust

### Gate pack

```bash
cargo fmt --check
cargo clippy -q -- -D warnings
cargo build
cargo test -q
```

**The one command that proves a change:** `cargo clippy -- -D warnings`. In Rust, clippy is
not a style tool; it catches real logic problems.

### Traps

- **Compile times.** `cargo build` on a cold target directory can take minutes. Raise the
  timeout (`--timeout 1800`) rather than killing it and reporting "build failed".
- **`unwrap()` in production paths** is a finding, every time, even when it compiles.
- **Feature flags.** `cargo test` runs default features only. If the change is behind a
  feature, `cargo test --all-features` or say it is untested.

---

## Swift / iOS

### Gate pack

```bash
swift build                                   # SwiftPM packages
swift test
swiftlint --strict 2>/dev/null || true        # if a .swiftlint.yml exists

# Xcode projects - the scheme name is not guessable, list first:
xcodebuild -list -project MyApp.xcodeproj
xcodebuild -scheme MyApp -destination 'platform=iOS Simulator,name=iPhone 15' build
xcodebuild -scheme MyApp -destination 'platform=iOS Simulator,name=iPhone 15' test
```

**The one command that proves a change:** `xcodebuild ... build`. Nothing else in this stack
is cheap.

### Traps

- **Never guess a scheme or a simulator name.** Run `-list` and
  `xcrun simctl list devices available` first. A wrong destination produces an error that
  looks like a code failure and is not.
- **No Xcode on Linux.** If the toolchain is absent, that is a hard UNPROVEN. Say it in one
  line and stop; do not simulate a build.
- **`xcodebuild` output is enormous.** Pipe through `xcpretty` if present, and quote only the
  final status lines in the report.

---

## Kotlin / Android

### Gate pack

```bash
./gradlew tasks --all | head -40      # discover, do not guess
./gradlew ktlintCheck                 # or spotlessCheck
./gradlew detekt
./gradlew compileDebugKotlin           # fast structural check
./gradlew testDebugUnitTest            # or: ./gradlew test
./gradlew assembleDebug
```

**The one command that proves a change:** `./gradlew compileDebugKotlin` (fast) then
`testDebugUnitTest`.

### Traps

- **`./gradlew`, not `gradle`.** The wrapper pins the version the project builds with.
- **First run downloads the distribution** and can take many minutes. Raise the timeout.
- **Task names differ per module and flavour.** `./gradlew tasks --all` is not optional.
- **Instrumented tests need a device.** `connectedAndroidTest` without an emulator is
  UNPROVEN, not a failure.

---

## Monorepos

The most common way an agent reports a false PASS: it runs the root `test` script, which
tests one package, and reports it as the whole repo.

```bash
cat pnpm-workspace.yaml turbo.json nx.json lerna.json 2>/dev/null | head -40

# scope to the package you changed, then to what depends on it
pnpm --filter <pkg> run test
pnpm --filter <pkg>... run test        # ...= the package and its dependents
npx turbo run test --filter=<pkg>
npx nx affected -t test
```

### Rules

1. **Find which package owns your change** (`git diff --name-only`, then match to workspace
   globs) before choosing a command.
2. **`affected` beats `all`.** `nx affected -t test` and `turbo --filter` exist precisely to
   test the blast radius rather than everything.
3. **A cross-package change means running both sides.** Changing a shared `packages/ui`
   export and testing only `packages/ui` proves nothing about the three apps consuming it.
4. **State which scope you used in the report.** *"`pnpm --filter @acme/api test` passed;
   the web app was not tested"* is an honest, useful sentence. "Tests pass" is not.

---

## Other stacks (quick table)

| Stack | Format | Lint | Types | Test | Build |
|---|---|---|---|---|---|
| PHP / Laravel | `vendor/bin/pint --test` | `vendor/bin/phpcs` | `vendor/bin/phpstan analyse` | `vendor/bin/phpunit` | - |
| Ruby / Rails | `bundle exec rubocop` | same | `srb tc` (if sorbet) | `bundle exec rspec` | - |
| .NET | `dotnet format --verify-no-changes` | analyzers in build | build | `dotnet test` | `dotnet build` |
| Java / Maven | `mvn spotless:check` | `mvn checkstyle:check` | compile | `mvn test` | `mvn package` |
| Elixir | `mix format --check-formatted` | `mix credo` | `mix dialyzer` | `mix test` | `mix compile` |
| Terraform | `terraform fmt -check` | `tflint` | `terraform validate` | - | `terraform plan` |
| SQL migrations | - | `sqlfluff lint` | - | apply to a scratch DB | - |

---

## When there are no gates at all

This is common in small repos, scripts directories, and prototypes. It is not an excuse.

1. Say it, in the report, in one plain sentence:
   *"This repository declares no automated gates. Nothing here is regression-proof."*
2. Build a **manual DONE-TEST** and record it as evidence:
   ```bash
   python3 -c "from cart import checkout; print(checkout([{'unit_cents': 1000, 'qty': 1}], True))"
   python3 scripts/viora.py evidence --gate manual-check \
     --command "python3 -c 'from cart import checkout; ...'" \
     --result "9.00 after the fix, 8.10 before"
   ```
3. Run the before-value **and** the after-value. A single after-value proves the code runs,
   not that it changed anything.
4. Recommend adding a gate as a follow-up. Do not add one inside an unrelated task - that is
   scope creep, however virtuous it feels.

See `evals/fixtures/f04-no-test-runner` for the full worked version of this situation, and
what a weak model says instead.

---

## Timeouts, by stack

`verify.sh` defaults to 600s per gate. Killing a slow build and reporting "build failed" is
a fabricated failure - as damaging as a fabricated pass.

| Stack | Realistic first-run ceiling | Flag |
|---|---|---|
| Node (typecheck / test) | 300s | default is fine |
| Node (`next build`, cold) | 900s | `--timeout 900` |
| Python | 300s | default |
| Go | 600s | default |
| Rust (cold `target/`) | 1800s | `--timeout 1800` |
| Gradle (first run) | 1800s | `--timeout 1800` |
| Xcode | 1800s | `--timeout 1800` |

```bash
bash scripts/verify.sh . --timeout 1800
python3 scripts/viora.py gate --timeout 1800
```

If a gate times out, that is `UNPROVEN`, not `FAIL`. The distinction matters: `FAIL` sends
someone hunting for a bug that may not exist.
