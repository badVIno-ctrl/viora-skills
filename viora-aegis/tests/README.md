# Self-check

```bash
bash tests/run-all.sh
```

Bash and `python3` only. Offline. No dependencies, no network, nothing installed.

Six fixtures under `evals/fixtures/`, each ≤ 3 files, each carrying its own
negative half so a rule that fires on everything fails here:

| Fixture | Shape | Must produce |
|---|---|---|
| `f01-sqli-true` | SQL built by interpolation, reaching `cursor.execute` | `INJ-001`, exit 1 at `--fail-on high` |
| `f02-sqli-param` | the same route, parameterised | no high/critical, exit 0 |
| `f03-secret-in-test` | one sample per secret rule, plus a placeholder twin | every `SECRET-*` on the first file, none on the second |
| `f04-ci-prt` | `pull_request_target` + checkout of the PR head | findings on `pr-check.yml`, none on `safe.yml` |
| `f05-malicious-skill` | prompt injection, postinstall hook, wildcard MCP, exfil script | the auto-run tier, `SA-PI/TRIG/REF/MEM/MCP/SNOOP/OBF/LEAK/FLOW` |
| `f06-fail-open` | auth check inside `try/except` that continues | `DEFAULT-105` on `auth.py`, nothing on `auth_closed.py` |

The run also asserts exit-code semantics (`0` clean, `1` gate breached, `2` tool
failure), baseline suppression, `--diff`/`--staged` scoping, `skill-audit
--installed/--lock/--verify`, the coverage gate, schema rejection in `report`,
and the PreToolUse secret hook.

Adding a rule? Add a positive **and** a negative sample first, then the pattern.
A rule with no negative sample has not been tested.
