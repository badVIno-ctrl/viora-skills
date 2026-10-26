# QA: preview-2

QA FAILED: 1 fail, 1 warn, 3 manual; checklist 14/16 auto, 4 for the agent

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
| 9 | Captions synced (150 ms), no cut words, no overflow | OK |  |
| 10 | Loudness -14 LUFS (+-1.5), true peak <= -1 dBTP, no clipping | OK |  |
| 11 | Last frame matches the first or leads to part 2 | FAIL | end does not loop to the start and does not lead to part 2; loop is off |
| 12 | Titles 5-7 (<= 100 chars), one description, no long dashes, hashtags sane | OK |  |
| 13 | Visual review: contact sheet (2 fps) and densest moments | EYES | open and describe: contact-1.png, contact-2.png; qa-frames/dense-24.0.png, qa-frames/dense-23.5.png, qa-frames/dense-23.0.png |
| 14 | Without sound: retell the video from picture and captions only | EYES | retell using qa.md 'silent storyboard' |
| 15 | Different from the user's previous videos | OK | no previous videos in memory |
| + | Language, no long dashes, CTA rules, hook | OK |  |
| + | Edit: shots differ, no titles or credits, no black frames > 0.5 s | OK | 3/3 different shots, no text screens, longest black 0.0s |
| + | Cuts on strong beats (50 ms), slow-mo on the peak | OK | music is not beat-synced (audio.music.beat_sync is off) |
| + | Edit craft: full screen, link in the centre, speed curves, faces centred, drop on the line end | OK | no edit scenes |
| + | Effects: <= 3 flashes per second (WCAG 2.3.1), bars do not hide the hook, motivated effects | OK | no 1.3 effects; flashes max 0/s |
| + | Foreign footage has >= 2 author layers (one core), no long stretch without them, credits | WARN | foreign footage (ultimatum: video, prediction: video, payoff: video) with 0 author layer(s): add voice, thesis text, own footage or a comparison (author_layer); 26s of foreign footage without your voice or text |
| + | Independent banner motion and final QR | OK |  |
| + | Sequential SRT intervals | OK |  |
| + | Publication acceptance | EYES | context_before_reviewed not confirmed; context_after_reviewed not confirmed; first_word_complete not confirmed; last_word_complete not confirmed; thought_complete not confirmed; answer_complete not confirmed; natural_reaction_preserved not confirmed; audio_listened not confirmed; motion_reviewed not confirmed; audio_listened not confirmed; editorial_accepted not confirmed; sources_verified not confirmed; ui_overlay_reviewed not confirmed |

## Checklist (research, section 9)

| # | Item | Answer | How |
|---|---|---|---|
| 1 | First frame interesting, not black, not a logo | yes | auto |
| 2 | First line gives the result or a question, no greeting | yes | auto |
| 3 | Idea reads on the first frame, small and without sound | check | manual |
| 4 | Title: key words first, honest, <= 100 chars, <= 1 emoji | yes | auto |
| 5 | Cover: one focus, 3-5 words, readable at 320 px, contrast | yes | auto |
| 6 | Event every 2-3 s | yes | auto |
| 7 | No pause > 1 s without a visual event | yes | auto |
| 8 | Promise from the start is kept by the end | check | manual |
| 9 | No goodbye, the end loops or leads to part 2 | no | auto |
| 10 | Clear without sound, captions present | yes | auto |
| 11 | One call to action, after the value | yes | auto |
| 12 | Link/handle in the safe zone twice, QR scans | no | auto |
| 13 | Pinned comment and description ready | yes | auto |
| 14 | Profile ready (remind the user) | check | manual |
| 15 | Everything important inside the safe zone | yes | auto |
| 16 | No slop: glow, gradients, empty zones, default font | yes | auto |
| 17 | Texts in the right language, no long dashes | yes | auto |
| 18 | About -14 LUFS, voice over music | yes | auto |
| 19 | 'Altered or synthetic content' label checked | check | manual |
| 20 | Clearly different from previous videos | yes | auto |

## Silent storyboard (picture + captions only)

- 0.0s [video]  | Учёные, у вас / осталось 40 лет, / чтобы изобрести / бессмертие. / Либо я умираю.
- 10.8s [video]  | Причем я уверен, / что когда / я умру, / бессмертие изобретут / через день.
- 17.8s [video]  | Иван Усович был / последним человеком, / который умер.

## Agent must still do

1. Open the contact sheets and dense frames, write what you saw (item 13).
2. Retell the video from the storyboard without sound (item 14).
3. Answer the manual checklist items (3, 8, 14, 19) honestly.
