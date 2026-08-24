<#
  Viora Aegis installer (Windows PowerShell / pwsh)
  One security skill, every coding agent.

  Usage:
    pwsh ./install.ps1                 auto-detect agents in this project
    pwsh ./install.ps1 -All            write adapters for every supported agent
    pwsh ./install.ps1 -Agent codex    install for one agent (repeatable, comma-separated)
    pwsh ./install.ps1 -Global         also install to user-level directories
    pwsh ./install.ps1 -DryRun         show what would change
    pwsh ./install.ps1 -Uninstall      remove pointer blocks and the installed pack
#>
[CmdletBinding()]
param(
  [switch]$All,
  [string[]]$Agent = @(),
  [switch]$Global,
  [switch]$DryRun,
  [switch]$Uninstall,
  [string]$Target = (Get-Location).Path
)

$ErrorActionPreference = 'Stop'
$Version  = '1.0.0'
$Src      = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackRel  = '.viora/skills/viora-aegis'
$Start    = '<!-- VIORA-AEGIS:START -->'
$End      = '<!-- VIORA-AEGIS:END -->'

function Say  ($m) { Write-Host $m }
function Step ($m) { Write-Host "  [ok] $m"   -ForegroundColor Green }
function Skip ($m) { Write-Host "  [--] $m"   -ForegroundColor DarkGray }
function Warn ($m) { Write-Host "  [!!] $m"   -ForegroundColor Yellow }

function Get-PointerBlock {
  @"
$Start
## Security - Viora Aegis

This project uses the **Viora Aegis** security skill.

**Read ``$PackRel/SKILL.md`` and follow it whenever you:**
- write or modify code touching untrusted input, authentication, authorization, sessions, payments,
  file uploads, personal data, or outbound requests;
- are asked to check, audit, harden, or "make secure" anything;
- prepare a commit, pull request, release, or deploy;
- triage a vulnerability report or scanner finding;
- review dependencies, Dockerfiles, CI workflows, or infrastructure;
- build LLM or agent features with tools, RAG, memory, or MCP.

Announce the mode you pick (GUARD / REVIEW / AUDIT / HARDEN / FIX / TRIAGE / DESIGN / AGENT-SEC).
A pattern match is a lead, not a finding: trace attacker-controlled input to a reachable sink, then
give a verdict and a fix with a verification step. Severity = impact x reachability.
Never weaken a security control to make a build or test pass. Ask before changing authentication,
authorization, CORS, crypto, or payment behaviour. Say what you did not check.

``````bash
python3 $PackRel/scripts/viora.py doctor  --path .
python3 $PackRel/scripts/viora.py scan    --path . --diff origin/main
python3 $PackRel/scripts/viora.py scan    --path . --fail-on high
python3 $PackRel/scripts/viora.py deps    --path .
``````
$End
"@
}

function Write-Block([string]$File) {
  $rel = $File.Replace($Target, '').TrimStart('\','/')
  if ($DryRun) { Skip "would update $rel"; return }

  $dir = Split-Path -Parent $File
  if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

  $block = Get-PointerBlock
  if (Test-Path $File) {
    $text = Get-Content -Raw -Path $File
    if ($text -match [regex]::Escape($Start)) {
      $pattern = [regex]::Escape($Start) + '[\s\S]*?' + [regex]::Escape($End)
      $text = [regex]::Replace($text, $pattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $block })
      Set-Content -Path $File -Value $text -Encoding UTF8 -NoNewline
      Step "updated $rel"
    } else {
      Add-Content -Path $File -Value "`n$block`n" -Encoding UTF8
      Step "appended to $rel"
    }
  } else {
    Set-Content -Path $File -Value "$block`n" -Encoding UTF8
    Step "created $rel"
  }
}

function Remove-Block([string]$File) {
  if (-not (Test-Path $File)) { return }
  $text = Get-Content -Raw -Path $File
  if ($text -notmatch [regex]::Escape($Start)) { return }
  $rel = $File.Replace($Target, '').TrimStart('\','/')
  if ($DryRun) { Skip "would clean $rel"; return }
  $pattern = '\r?\n?' + [regex]::Escape($Start) + '[\s\S]*?' + [regex]::Escape($End) + '\r?\n?'
  Set-Content -Path $File -Value ([regex]::Replace($text, $pattern, "`n")) -Encoding UTF8 -NoNewline
  Step "cleaned $rel"
}

function Copy-Pack([string]$Dest) {
  $rel = $Dest.Replace($Target, '').TrimStart('\','/')
  if ($DryRun) { Skip "would copy pack -> $rel"; return }
  if ((Resolve-Path -ErrorAction SilentlyContinue $Dest).Path -eq $Src) { Skip "pack already at $rel"; return }
  New-Item -ItemType Directory -Force -Path $Dest | Out-Null
  Get-ChildItem -Path $Src -Recurse -File |
    Where-Object { $_.FullName -notmatch '__pycache__' -and $_.FullName -notmatch '\\\.git\\' } |
    ForEach-Object {
      $rp  = $_.FullName.Substring($Src.Length).TrimStart('\','/')
      $out = Join-Path $Dest $rp
      $od  = Split-Path -Parent $out
      if (-not (Test-Path $od)) { New-Item -ItemType Directory -Force -Path $od | Out-Null }
      Copy-Item $_.FullName $out -Force
    }
  Step "pack -> $rel"
}

function Copy-One([string]$From, [string]$To) {
  $rel = $To.Replace($Target, '').TrimStart('\','/')
  if ($DryRun) { Skip "would write $rel"; return }
  $dir = Split-Path -Parent $To
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Copy-Item $From $To -Force
  Step $rel
}

function Test-Has([string]$P) { Test-Path (Join-Path $Target $P) }

function Get-Detected {
  $f = @()
  if (Test-Has '.claude')        { $f += 'claude-code' }
  if (Test-Has 'AGENTS.md')      { $f += 'codex' }
  if (Test-Has '.codex')         { $f += 'codex' }
  if (Test-Has '.antigravity')   { $f += 'antigravity' }
  if (Test-Has '.cursor')        { $f += 'cursor' }
  if (Test-Has '.windsurf')      { $f += 'windsurf' }
  if (Test-Has 'GEMINI.md')      { $f += 'gemini' }
  if (Test-Has '.gemini')        { $f += 'gemini' }
  if (Test-Has '.github')        { $f += 'copilot' }
  if (Test-Has '.opencode')      { $f += 'opencode' }
  if (Test-Has '.clinerules')    { $f += 'cline' }
  if (Test-Has '.roo')           { $f += 'roo' }
  if (Test-Has '.kilocode')      { $f += 'kilo' }
  if (Test-Has '.continue')      { $f += 'continue' }
  if (Test-Has 'CONVENTIONS.md') { $f += 'aider' }
  $f | Select-Object -Unique
}

function Install-Agent([string]$a) {
  switch ($a) {
    'claude-code' { Copy-Pack (Join-Path $Target '.claude/skills/viora-aegis') }
    'opencode'    { Copy-Pack (Join-Path $Target '.opencode/skills/viora-aegis') }
    'codex'       { Write-Block (Join-Path $Target 'AGENTS.md') }
    'antigravity' { Copy-One (Join-Path $Src 'adapters/antigravity.md') (Join-Path $Target '.antigravity/rules/viora-aegis.md')
                    Write-Block (Join-Path $Target 'AGENTS.md') }
    'cursor'      { Copy-One (Join-Path $Src 'adapters/cursor.mdc')  (Join-Path $Target '.cursor/rules/viora-aegis.mdc') }
    'windsurf'    { Copy-One (Join-Path $Src 'adapters/windsurf.md') (Join-Path $Target '.windsurf/rules/viora-aegis.md') }
    'gemini'      { Write-Block (Join-Path $Target 'GEMINI.md') }
    'copilot'     { Write-Block (Join-Path $Target '.github/copilot-instructions.md') }
    'cline'       { Copy-One (Join-Path $Src 'SKILL.md') (Join-Path $Target '.clinerules/viora-aegis.md') }
    'roo'         { Copy-One (Join-Path $Src 'SKILL.md') (Join-Path $Target '.roo/rules/viora-aegis.md') }
    'kilo'        { Copy-One (Join-Path $Src 'SKILL.md') (Join-Path $Target '.kilocode/rules/viora-aegis.md') }
    'continue'    { Copy-One (Join-Path $Src 'SKILL.md') (Join-Path $Target '.continue/rules/viora-aegis.md') }
    'aider'       { Write-Block (Join-Path $Target 'CONVENTIONS.md') }
    'zed'         { Write-Block (Join-Path $Target '.rules') }
    'generic'     { Write-Block (Join-Path $Target 'AGENTS.md') }
    default       { Warn "unknown agent: $a" }
  }
}

Say ''
Say "Viora Aegis v$Version - universal security skill"
Say "target: $Target"
Say ''

if ($Uninstall) {
  Say 'Uninstalling'
  @('.claude/skills/viora-aegis','.opencode/skills/viora-aegis',$PackRel) | ForEach-Object {
    $p = Join-Path $Target $_
    if (Test-Path $p) { if (-not $DryRun) { Remove-Item -Recurse -Force $p }; Step "removed $_" }
  }
  @('.cursor/rules/viora-aegis.mdc','.windsurf/rules/viora-aegis.md','.antigravity/rules/viora-aegis.md',
    '.clinerules/viora-aegis.md','.roo/rules/viora-aegis.md','.kilocode/rules/viora-aegis.md',
    '.continue/rules/viora-aegis.md') | ForEach-Object {
    $p = Join-Path $Target $_
    if (Test-Path $p) { if (-not $DryRun) { Remove-Item -Force $p }; Step "removed $_" }
  }
  @('AGENTS.md','GEMINI.md','CONVENTIONS.md','.rules','.github/copilot-instructions.md') | ForEach-Object {
    Remove-Block (Join-Path $Target $_)
  }
  Say ''; Say 'Done.'; exit 0
}

Say '1. Installing the pack'
Copy-Pack (Join-Path $Target $PackRel)

Say ''
Say '2. Wiring agents'
$list = @()
if     ($All)             { $list = @('claude-code','codex','antigravity','cursor','windsurf','gemini','copilot','opencode','cline','roo','kilo','continue','aider','zed') }
elseif ($Agent.Count -gt 0) { $list = $Agent }
else {
  $list = @(Get-Detected)
  if ($list.Count -eq 0) { Warn 'no agent config detected - writing the universal AGENTS.md pointer'; $list = @('generic') }
  else { Say "   detected: $($list -join ', ')"; $list += 'generic' }
}
foreach ($a in ($list | Select-Object -Unique)) { Install-Agent $a }

if ($Global) {
  Say ''
  Say '3. Global (user-level)'
  if ($DryRun) { Skip 'would install to ~/.claude/skills and ~/.viora/skills' }
  else {
    Copy-Pack (Join-Path $HOME '.claude/skills/viora-aegis')
    Copy-Pack (Join-Path $HOME '.viora/skills/viora-aegis')
  }
}

Say ''
Say '4. Verifying'
$py = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if ($py) {
  Step "python: $($py.Source)"
  if (-not $DryRun) {
    & $py.Source (Join-Path $Target "$PackRel/scripts/viora.py") --version *> $null
    if ($LASTEXITCODE -eq 0) { Step 'CLI works' } else { Warn 'CLI did not start - the skill still works in grep-only mode' }
  }
} else {
  Warn 'python not found - the skill works in grep-only mode (rules/*.json are plain regexes)'
}

Say ''
Say 'Installed. Next:'
Say "  python3 $PackRel/scripts/viora.py doctor --path ."
Say '  then ask your agent: "Run a Viora Aegis review of this project"'
Say ''
