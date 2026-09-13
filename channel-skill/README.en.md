<div align="center">

# CHANNEL SKILL

**An agent skill that writes Telegram posts in your own voice.**

It interviews you first, then writes. Not the other way around.

MIT license, version 6.1.0, python 3.8+, zero external dependencies

[Russian README](README.md) - [Quickstart](docs/QUICKSTART.md) - [Profile](docs/PROFILE.md) - [Telegram](docs/TELEGRAM.md) - [Architecture](docs/ARCHITECTURE.md) - [FAQ](docs/FAQ.md)

</div>

> The skill itself speaks Russian by default, because it was born in a Russian
> Telegram channel. Set brand.language in your profile to write in another
> language. This page is a short English map of the repository.

## The problem

Any model can produce a post. The problem is that the post is not yours:
long dashes everywhere, empty intros, invented numbers, a borrowed tone,
a different footer every time, and a wall of text where Telegram needs a split.

CHANNEL SKILL covers the whole chain: learn the author, pick a rubric and a frame,
write, lint, score against the real numbers of your channel, hand back a clean draft.
A human still presses publish.

## What makes it different: the skill asks first

The first run is not a text, it is a 5 to 7 minute interview: who you are, what the
channel is about, who reads it, your tone, your rubrics, the links in your footer.
Answers are stored in a profile, and every rule, length corridor and footer is derived
from it.

```bash
cd channel-skill
python3 tools/onboard.py            # interactive interview
python3 tools/onboard.py --questions # JSON questions, for an agent to ask in chat
python3 tools/profile.py --check     # validate the result
```

Three ways to fill the profile: the terminal interview, an agent asking in chat
(`--questions` then `--stdin`), or copying a ready template from
`channel-skill/profile/profiles` and editing it by hand.

## Quickstart

```bash
git clone https://github.com/OWNER/channel-skill.git
cd channel-skill/channel-skill
python3 tools/onboard.py
python3 tools/profile.py --check
# ask your agent: write a post about X in rubric Y
python3 tools/channel.py ship draft.txt --rubric guide
```

`ship` runs autofix, the post linter, the score and the splitter in one pass.

## What is inside

| Block | What it does |
| --- | --- |
| Interview | Builds the author profile and renders it into every file of the skill |
| Router | Picks rubric, frame, length corridor and the single file to read |
| Post linter | Catches bare links, wrong footer, missing hashtag, AI tells |
| Autofix | Fixes what can be fixed mechanically, lists the rest |
| Score | Grades a draft against the reach and reactions of your channel |
| Splitter | Cuts a long text into a post plus a telegra.ph article |
| Research and video | Finds facts and reads video subtitles without paid keys |
| Channel memory | Remembers past greetings, topics and decisions |
| Telegram bridge | Task in from Saved Messages, draft back. Your own keys |

## Supported agents

Any agent that reads files and runs python3:

- Claude Code and any Agent Skills host: `.claude-plugin/plugin.json`, `CLAUDE.md`
- Codex: `.codex-plugin/plugin.json`, `AGENTS.md`
- Cursor: the root rules file and `.cursor/rules/channel-skill.mdc`
- Gemini and others: `GEMINI.md`
- No file access: paste `channel-skill/PROMPT-CORE.txt` into the first message

Install into another project:

```bash
cd channel-skill
python3 tools/install.py --target /path/to/project --dry-run
python3 tools/install.py --target /path/to/project
```

## Bring your own Telegram

The bridge is optional. With it you send a task to your own Saved Messages and get
the draft back in the same chat.

```bash
cp secrets/telegram.env.example secrets/telegram.env   # api_id and api_hash from my.telegram.org
python3 channel-skill/tools/tg.py setup
python3 channel-skill/tools/tg.py doctor
```

No keys, tokens or sessions are committed. Everything in `secrets` is an example file,
real ones are ignored by git. Details in [docs/TELEGRAM.md](docs/TELEGRAM.md).

## Quality gate

```bash
cd channel-skill
bash tools/check_all.sh
```

Selftests for every script, behaviour evals, single source prompt build, delivery
manifest check and a long dash hunt. The same command runs in CI on every push.

## License

MIT, see [LICENSE](LICENSE). Take it, change it, run your own channel.
