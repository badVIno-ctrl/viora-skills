#!/usr/bin/env bash
# Viora Build - combined gate.
#
# Calls the checks that ship with viora-design-skills, viora-code-protocol and
# viora-aegis, then prints one evidence table. Holds no rules of its own and
# never edits your source; logs are written under <project>/.viora/build/.
#
# Usage:
#   bash pipeline_check.sh [project-dir] [--only design,code,security] [--quiet]
#   VIORA_SKILLS_DIR=~/.claude/skills bash pipeline_check.sh .
#
# Exit: 0 all executed gates passed, 1 at least one failed, 2 bad usage.

set -u

PROJECT="."
ONLY="design,code,security"
QUIET=0

while [ $# -gt 0 ]; do
	case "$1" in
		--only) ONLY="${2:-}"; shift 2 ;;
		--quiet) QUIET=1; shift ;;
		-h|--help) sed -n '2,13p' "$0"; exit 0 ;;
		-*) echo "unknown flag: $1" >&2; exit 2 ;;
		*) PROJECT="$1"; shift ;;
	esac
done

[ -d "$PROJECT" ] || { echo "not a directory: $PROJECT" >&2; exit 2; }
PROJECT="$(cd "$PROJECT" && pwd)"
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
PACK_DIR="$(dirname "$SELF_DIR")"
SIBLINGS="$(dirname "$PACK_DIR")"
LOG_DIR="$PROJECT/.viora/build"
mkdir -p "$LOG_DIR"

ROWS=""
FAILED=0
RAN=0

has() { command -v "$1" >/dev/null 2>&1; }
wants() { case ",$ONLY," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

find_pack() {
	pack="$1"
	OLD_IFS="$IFS"
	IFS='
'
	for base in \
		"${VIORA_SKILLS_DIR:-}" \
		"$SIBLINGS" \
		"$PROJECT" \
		"$PROJECT/.claude/skills" \
		"$PROJECT/.viora/skills" \
		"$PROJECT/.codex/skills" \
		"$PROJECT/.opencode/skills" \
		"$HOME/.claude/skills" \
		"$HOME/.viora/skills"
	do
		[ -n "$base" ] && [ -d "$base/$pack" ] && { printf '%s\n' "$base/$pack"; IFS="$OLD_IFS"; return 0; }
	done
	IFS="$OLD_IFS"
	return 1
}

row() { ROWS="$ROWS$1|$2|$3
"; }

skip() { row "$1" "$2" "SKIPPED"; }

run() { # run <label> <logname> <cmd...>
	label="$1"; logname="$2"; shift 2
	log="$LOG_DIR/$logname.log"
	[ "$QUIET" -eq 1 ] || printf '\n\033[1m>> %s\033[0m\n' "$label"
	if has timeout; then timeout 900 "$@" >"$log" 2>&1; status=$?
	else "$@" >"$log" 2>&1; status=$?; fi
	RAN=$((RAN + 1))
	if [ $status -eq 0 ]; then
		row "$label" "$logname" "PASS"
		[ "$QUIET" -eq 1 ] || tail -n 3 "$log"
	else
		FAILED=$((FAILED + 1))
		row "$label" "$logname" "FAIL ($status)"
		[ "$QUIET" -eq 1 ] || tail -n 20 "$log"
	fi
}

DESIGN="$(find_pack viora-design-skills || true)"
CODE="$(find_pack viora-code-protocol || true)"
AEGIS="$(find_pack viora-aegis || true)"

# --- design ---------------------------------------------------------------
if wants design; then
	if [ -z "$DESIGN" ]; then skip "design: checker" "pack viora-design-skills not found"
	elif ! has node; then skip "design: checker" "node not available"
	else
		run "design: checker" "design-check" node "$DESIGN/scripts/check.mjs" "$PROJECT"
		TOKENS="$(find "$PROJECT" -maxdepth 3 -name 'tokens.css' -not -path '*/node_modules/*' -not -path '*/.viora/*' 2>/dev/null | head -n 1)"
		if [ -n "$TOKENS" ]; then
			run "design: contrast" "design-contrast" node "$DESIGN/scripts/contrast.mjs" "$TOKENS"
		else
			skip "design: contrast" "no tokens.css found"
		fi
	fi
fi

# --- code -----------------------------------------------------------------
if wants code; then
	if [ -z "$CODE" ]; then skip "code: gates" "pack viora-code-protocol not found"
	else
		if has python3; then
			run "code: duplicates" "code-duplicates" python3 "$CODE/scripts/find_duplicates.py" "$PROJECT"
			run "code: ui guard" "code-ui-guard" python3 "$CODE/scripts/ui_guard.py" "$PROJECT"
		else
			skip "code: duplicates" "python3 not available"
			skip "code: ui guard" "python3 not available"
		fi
		if [ -f "$CODE/scripts/verify.sh" ]; then
			run "code: repo gates" "code-verify" bash "$CODE/scripts/verify.sh" "$PROJECT"
		else
			skip "code: repo gates" "verify.sh missing"
		fi
	fi
fi

# --- security -------------------------------------------------------------
if wants security; then
	if [ -z "$AEGIS" ]; then skip "security: scan" "pack viora-aegis not found"
	elif ! has python3; then skip "security: scan" "python3 not available"
	else
		run "security: scan" "security-scan" python3 "$AEGIS/scripts/viora.py" scan --path "$PROJECT" --format text
		run "security: deps" "security-deps" python3 "$AEGIS/scripts/viora.py" deps --path "$PROJECT"
	fi
fi

# --- table ----------------------------------------------------------------
printf '\n\033[1mViora Build - combined gate\033[0m\n'
printf 'project: %s\nlogs:    %s\n\n' "$PROJECT" "$LOG_DIR"
printf '| %-20s | %-34s | %-9s |\n' "Gate" "Log / reason" "Result"
printf '|%s|%s|%s|\n' "----------------------" "------------------------------------" "-----------"
printf '%s' "$ROWS" | while IFS='|' read -r a b c; do
	[ -n "$a" ] && printf '| %-20s | %-34s | %-9s |\n' "$a" "$b" "$c"
done

printf '\n'
if [ "$RAN" -eq 0 ]; then
	echo "UNPROVEN: no gate could run - install the packs or check node/python3."
	exit 1
fi
if [ "$FAILED" -gt 0 ]; then
	echo "$FAILED of $RAN gates failed. Open the logs above; do not claim completion."
	exit 1
fi
echo "All $RAN executed gates passed. Skipped rows stay UNPROVEN in the report."
exit 0
