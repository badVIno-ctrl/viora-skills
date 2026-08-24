#!/usr/bin/env bash
# Viora Aegis installer — one security skill, every coding agent.
# Usage:
#   bash install.sh                  auto-detect agents in this project
#   bash install.sh --all            write adapters for every supported agent
#   bash install.sh --agent codex    install for one agent (repeatable)
#   bash install.sh --global         also install to user-level directories
#   bash install.sh --dry-run        show what would change
#   bash install.sh --uninstall      remove pointer blocks and the installed pack
set -euo pipefail

VERSION="1.0.0"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_ROOT="$(pwd)"
PACK_REL=".viora/skills/viora-aegis"
START="<!-- VIORA-AEGIS:START -->"
END="<!-- VIORA-AEGIS:END -->"

ALL=0; GLOBAL=0; DRY=0; UNINSTALL=0
AGENTS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --all)       ALL=1 ;;
    --global)    GLOBAL=1 ;;
    --dry-run)   DRY=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --agent)     shift; AGENTS+=("${1:-}") ;;
    --target)    shift; TARGET_ROOT="${1:-$(pwd)}" ;;
    -h|--help)   sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ -t 1 ]; then B="\033[1m"; G="\033[32m"; Y="\033[33m"; D="\033[2m"; R="\033[0m"
else B=""; G=""; Y=""; D=""; R=""; fi

say()  { printf "%b\n" "$*"; }
step() { printf "  ${G}✓${R} %s\n" "$*"; }
skip() { printf "  ${D}· %s${R}\n" "$*"; }
warn() { printf "  ${Y}!${R} %s\n" "$*"; }

# ---------------------------------------------------------------- pointer text
pointer_block() {
  local pack="$1"
  cat <<EOF
$START
## Security — Viora Aegis

This project uses the **Viora Aegis** security skill.

**Read \`$pack/SKILL.md\` and follow it whenever you:**
- write or modify code touching untrusted input, authentication, authorization, sessions, payments,
  file uploads, personal data, or outbound requests;
- are asked to check, audit, harden, or "make secure" anything;
- prepare a commit, pull request, release, or deploy;
- triage a vulnerability report or scanner finding;
- review dependencies, Dockerfiles, CI workflows, or infrastructure;
- build LLM or agent features with tools, RAG, memory, or MCP.

Announce the mode you pick (GUARD / REVIEW / AUDIT / HARDEN / FIX / TRIAGE / DESIGN / AGENT-SEC).
A pattern match is a lead, not a finding: trace attacker-controlled input to a reachable sink, then
give a verdict and a fix with a verification step. Severity = impact × reachability.
Never weaken a security control to make a build or test pass. Ask before changing authentication,
authorization, CORS, crypto, or payment behaviour. Say what you did not check.

\`\`\`bash
python3 $pack/scripts/viora.py doctor  --path .
python3 $pack/scripts/viora.py scan    --path . --diff origin/main
python3 $pack/scripts/viora.py scan    --path . --fail-on high
python3 $pack/scripts/viora.py deps    --path .
\`\`\`
$END
EOF
}

# --------------------------------------------------------------- file plumbing
write_block() {           # write_block <file>
  local file="$1" tmp block
  block="$(pointer_block "$PACK_REL")"

  if [ "$DRY" = "1" ]; then skip "would update ${file#$TARGET_ROOT/}"; return; fi
  mkdir -p "$(dirname "$file")"

  if [ -f "$file" ] && grep -qF "$START" "$file" 2>/dev/null; then
    tmp="$(mktemp)"
    awk -v s="$START" -v e="$END" '
      index($0,s){skip=1} !skip{print} index($0,e){skip=0}
    ' "$file" > "$tmp"
    printf '%s\n' "$block" >> "$tmp"
    mv "$tmp" "$file"
    step "updated ${file#$TARGET_ROOT/}"
  elif [ -f "$file" ]; then
    printf '\n%s\n' "$block" >> "$file"
    step "appended to ${file#$TARGET_ROOT/}"
  else
    printf '%s\n' "$block" > "$file"
    step "created ${file#$TARGET_ROOT/}"
  fi
}

remove_block() {          # remove_block <file>
  local file="$1" tmp
  [ -f "$file" ] || return 0
  grep -qF "$START" "$file" || return 0
  if [ "$DRY" = "1" ]; then skip "would clean ${file#$TARGET_ROOT/}"; return; fi
  tmp="$(mktemp)"
  awk -v s="$START" -v e="$END" 'index($0,s){skip=1} !skip{print} index($0,e){skip=0}' "$file" > "$tmp"
  mv "$tmp" "$file"
  step "cleaned ${file#$TARGET_ROOT/}"
}

copy_pack() {             # copy_pack <destination dir>
  local dest="$1"
  if [ "$DRY" = "1" ]; then skip "would copy pack → ${dest#$TARGET_ROOT/}"; return; fi
  [ "$(cd "$dest" 2>/dev/null && pwd || echo x)" = "$SRC" ] && { skip "pack already at ${dest#$TARGET_ROOT/}"; return; }
  mkdir -p "$dest"
  # portable copy of contents, excluding VCS noise
  ( cd "$SRC" && find . -type d -name '.git' -prune -o -type d -name '__pycache__' -prune -o -type f -print ) \
  | while IFS= read -r f; do
      mkdir -p "$dest/$(dirname "$f")"
      cp "$SRC/$f" "$dest/$f"
    done
  chmod +x "$dest/scripts/viora.py" "$dest/install.sh" 2>/dev/null || true
  step "pack → ${dest#$TARGET_ROOT/}"
}

copy_file() {             # copy_file <src> <dest>
  if [ "$DRY" = "1" ]; then skip "would write ${2#$TARGET_ROOT/}"; return; fi
  mkdir -p "$(dirname "$2")"; cp "$1" "$2"; step "${2#$TARGET_ROOT/}"
}

has() { [ -e "$TARGET_ROOT/$1" ]; }

# ------------------------------------------------------------------- detection
detect() {
  local found=()
  has ".claude"        && found+=(claude-code)
  has "AGENTS.md"      && found+=(codex)
  has ".codex"         && found+=(codex)
  has ".antigravity"   && found+=(antigravity)
  has ".cursor"        && found+=(cursor)
  has ".windsurf"      && found+=(windsurf)
  has "GEMINI.md"      && found+=(gemini)
  has ".gemini"        && found+=(gemini)
  has ".github"        && found+=(copilot)
  has ".opencode"      && found+=(opencode)
  has ".clinerules"    && found+=(cline)
  has ".roo"           && found+=(roo)
  has ".kilocode"      && found+=(kilo)
  has ".continue"      && found+=(continue)
  has "CONVENTIONS.md" && found+=(aider)
  printf '%s\n' "${found[@]:-}" | awk 'NF' | sort -u
}

WRITTEN_BLOCKS=""
write_block_once() {
  case " $WRITTEN_BLOCKS " in
    *" $1 "*) return 0 ;;
  esac
  WRITTEN_BLOCKS="$WRITTEN_BLOCKS $1"
  write_block "$1"
}

install_agent() {
  local a="$1"
  case "$a" in
    claude-code) copy_pack "$TARGET_ROOT/.claude/skills/viora-aegis" ;;
    opencode)    copy_pack "$TARGET_ROOT/.opencode/skills/viora-aegis" ;;
    codex)       write_block_once "$TARGET_ROOT/AGENTS.md" ;;
    antigravity) copy_file "$SRC/adapters/antigravity.md" "$TARGET_ROOT/.antigravity/rules/viora-aegis.md"
                 write_block_once "$TARGET_ROOT/AGENTS.md" ;;
    cursor)      copy_file "$SRC/adapters/cursor.mdc"     "$TARGET_ROOT/.cursor/rules/viora-aegis.mdc" ;;
    windsurf)    copy_file "$SRC/adapters/windsurf.md"    "$TARGET_ROOT/.windsurf/rules/viora-aegis.md" ;;
    gemini)      write_block_once "$TARGET_ROOT/GEMINI.md" ;;
    copilot)     write_block_once "$TARGET_ROOT/.github/copilot-instructions.md" ;;
    cline)       copy_file "$SRC/SKILL.md" "$TARGET_ROOT/.clinerules/viora-aegis.md" ;;
    roo)         copy_file "$SRC/SKILL.md" "$TARGET_ROOT/.roo/rules/viora-aegis.md" ;;
    kilo)        copy_file "$SRC/SKILL.md" "$TARGET_ROOT/.kilocode/rules/viora-aegis.md" ;;
    continue)    copy_file "$SRC/SKILL.md" "$TARGET_ROOT/.continue/rules/viora-aegis.md" ;;
    aider)       write_block_once "$TARGET_ROOT/CONVENTIONS.md" ;;
    zed)         write_block_once "$TARGET_ROOT/.rules" ;;
    generic)     write_block_once "$TARGET_ROOT/AGENTS.md" ;;
    *) warn "unknown agent: $a" ;;
  esac
}

uninstall_agent() {
  rm -rf "$TARGET_ROOT/.claude/skills/viora-aegis" "$TARGET_ROOT/.opencode/skills/viora-aegis" 2>/dev/null || true
  rm -f  "$TARGET_ROOT/.cursor/rules/viora-aegis.mdc" "$TARGET_ROOT/.windsurf/rules/viora-aegis.md" \
         "$TARGET_ROOT/.antigravity/rules/viora-aegis.md" "$TARGET_ROOT/.clinerules/viora-aegis.md" \
         "$TARGET_ROOT/.roo/rules/viora-aegis.md" "$TARGET_ROOT/.kilocode/rules/viora-aegis.md" \
         "$TARGET_ROOT/.continue/rules/viora-aegis.md" 2>/dev/null || true
  for f in AGENTS.md GEMINI.md CONVENTIONS.md .rules .github/copilot-instructions.md; do
    remove_block "$TARGET_ROOT/$f"
  done
  rm -rf "$TARGET_ROOT/$PACK_REL"
  step "removed installed pack and pointer blocks"
}

# ------------------------------------------------------------------------ main
say ""
say "${B}Viora Aegis${R} v$VERSION — universal security skill"
say "${D}target: $TARGET_ROOT${R}"
say ""

if [ "$UNINSTALL" = "1" ]; then
  say "${B}Uninstalling${R}"
  uninstall_agent
  say ""; say "Done."; exit 0
fi

# 1. the pack itself
say "${B}1. Installing the pack${R}"
copy_pack "$TARGET_ROOT/$PACK_REL"

# 2. which agents
say ""
say "${B}2. Wiring agents${R}"

if [ "$ALL" = "1" ]; then
  LIST=(claude-code codex antigravity cursor windsurf gemini copilot opencode cline roo kilo continue aider zed)
elif [ ${#AGENTS[@]} -gt 0 ]; then
  LIST=("${AGENTS[@]}")
else
  LIST=()
  while IFS= read -r line; do
    [ -n "$line" ] && LIST+=("$line")
  done <<EOF
$(detect)
EOF
  if [ ${#LIST[@]} -eq 0 ]; then
    warn "no agent config detected — writing the universal AGENTS.md pointer"
    LIST=(generic)
  else
    say "${D}detected: ${LIST[*]}${R}"
    LIST+=(generic)
  fi
fi

for a in "${LIST[@]}"; do install_agent "$a"; done

# 3. global
if [ "$GLOBAL" = "1" ]; then
  say ""
  say "${B}3. Global (user-level)${R}"
  if [ "$DRY" = "1" ]; then
    skip "would install to ~/.claude/skills and ~/.viora/skills"
  else
    copy_pack "$HOME/.claude/skills/viora-aegis"
    copy_pack "$HOME/.viora/skills/viora-aegis"
    step "global pack installed"
  fi
fi

# 4. gitignore for working files
if [ "$DRY" != "1" ] && [ -d "$TARGET_ROOT/.git" ]; then
  GI="$TARGET_ROOT/.gitignore"
  grep -qs '^\.viora/findings' "$GI" 2>/dev/null || {
    printf '\n# Viora Aegis working files\n.viora/findings.*\n.viora/baseline.json\n.viora/*.sarif\n' >> "$GI"
  }
fi

# 5. verify
say ""
say "${B}4. Verifying${R}"
if command -v python3 >/dev/null 2>&1; then
  PYV="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo '?')"
  step "python3 $PYV"
  if [ "$DRY" != "1" ]; then
    python3 "$TARGET_ROOT/$PACK_REL/scripts/viora.py" --version >/dev/null 2>&1 \
      && step "CLI works" || warn "CLI did not start — the skill still works in grep-only mode"
  fi
else
  warn "python3 not found — the skill works in grep-only mode (rules/*.json are plain regexes)"
fi

say ""
say "${B}Installed.${R} Next:"
say "  python3 $PACK_REL/scripts/viora.py doctor --path ."
say "  ${D}then ask your agent:${R} \"Run a Viora Aegis review of this project\""
say ""
say "${D}Optional gates:  python3 $PACK_REL/scripts/viora.py init --hook --ci github${R}"
say ""
