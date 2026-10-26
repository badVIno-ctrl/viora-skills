# QA: ad-video-training

QA PASSED: 0 fail, 2 warn, 2 manual; checklist 12/15 auto, 5 for the agent

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | Format: 1080x1920, H.264/AAC, native 24/25/30/50/60 fps, duration in target | OK |  |
| 2 | First frame is not empty, motion in the first 1.5 s | OK |  |
| 3 | Event at least every 3 s, no still pause > 1 s | OK |  |
| 4 | Text, QR and links inside the platform safe zone | OK |  |
| 5 | Text contrast and minimum font sizes | OK |  |
| 6 | Centre >= 55% of height, no empty zone > 15%, panels filled | OK |  |
| 7 | No glow, no gradient plates, <= 3 colours, no default font, no emoji | OK |  |
| 8 | QR decodes from the finished video and matches the link | OK | Animated banner QR is decoded by the independent live_banner check |
| 9 | Captions synced (150 ms), no cut words, no overflow | WARN | 22% single-word chunks (target <= 20%) |
| 10 | Loudness -14 LUFS (+-1.5), true peak <= -1 dBTP, no clipping | OK |  |
| 11 | Last frame matches the first or leads to part 2 | OK |  |
| 12 | Titles 5-7 (<= 100 chars), one description, no long dashes, hashtags sane | WARN | metadata.json missing: run `shorts.py meta DIR` |
| 13 | Visual review: contact sheet (2 fps) and densest moments | EYES | open and describe: contact-1.png; qa-frames/dense-11.5.png, qa-frames/dense-11.0.png, qa-frames/dense-10.5.png |
| 14 | Without sound: retell the video from picture and captions only | EYES | retell using qa.md 'silent storyboard' |
| 15 | Different from the user's previous videos | OK |  |
| + | Language, no long dashes, CTA rules, hook | OK |  |
| + | Edit: shots differ, no titles or credits, no black frames > 0.5 s | OK | not an edit (no film/video scenes) |
| + | Cuts on strong beats (50 ms), slow-mo on the peak | OK | music is not beat-synced (audio.music.beat_sync is off) |
| + | Edit craft: full screen, link in the centre, speed curves, faces centred, drop on the line end | OK | no edit scenes |
| + | Effects: <= 3 flashes per second (WCAG 2.3.1), bars do not hide the hook, motivated effects | OK | no 1.3 effects; flashes max 0/s |
| + | Foreign footage has >= 2 author layers (one core), no long stretch without them, credits | OK | no foreign footage |
| + | Independent banner motion and final QR | OK |  |
| + | Sequential SRT intervals | OK |  |

## Checklist (research, section 9)

| # | Item | Answer | How |
|---|---|---|---|
| 1 | First frame interesting, not black, not a logo | yes | auto |
| 2 | First line gives the result or a question, no greeting | yes | auto |
| 3 | Idea reads on the first frame, small and without sound | check | manual |
| 4 | Title: key words first, honest, <= 100 chars, <= 1 emoji | no | auto |
| 5 | Cover: one focus, 3-5 words, readable at 320 px, contrast | check | manual |
| 6 | Event every 2-3 s | yes | auto |
| 7 | No pause > 1 s without a visual event | yes | auto |
| 8 | Promise from the start is kept by the end | check | manual |
| 9 | No goodbye, the end loops or leads to part 2 | yes | auto |
| 10 | Clear without sound, captions present | yes | auto |
| 11 | One call to action, after the value | yes | auto |
| 12 | Link/handle in the safe zone twice, QR scans | no | auto |
| 13 | Pinned comment and description ready | no | auto |
| 14 | Profile ready (remind the user) | check | manual |
| 15 | Everything important inside the safe zone | yes | auto |
| 16 | No slop: glow, gradients, empty zones, default font | yes | auto |
| 17 | Texts in the right language, no long dashes | yes | auto |
| 18 | About -14 LUFS, voice over music | yes | auto |
| 19 | 'Altered or synthetic content' label checked | check | manual |
| 20 | Clearly different from previous videos | yes | auto |

## Silent storyboard (picture + captions only)

- 0.0s [html]  | Одно пропущенное / слово меняет / смысл текста.
- 4.2s [html]  | Редактор-пример / подсвечивает / отличие от оригинала.
- 8.9s [html]  | Сверь свой текст / с оригиналом / перед публикацией.

## Agent must still do

1. Open the contact sheets and dense frames, write what you saw (item 13).
2. Retell the video from the storyboard without sound (item 14).
3. Answer the manual checklist items (3, 8, 14, 19) honestly.
