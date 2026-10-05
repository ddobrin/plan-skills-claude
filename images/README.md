# images/

Four visual introductions to plan-swarm@3.0. Each one targets a different audience. All of them show the same loop, from intent to release.

| Folder | Artifact | Best for | Format |
|---|---|---|---|
| `lifecycle/` | The loop: 10 stages in a ring, the typed approval phrase at each human gate, and the Path A rework arc. Three forms from one source: a fast GIF, a click-through **stepper**, and an explainer-pace **MP4** | GIF: README header, chat. Stepper: presenting and explaining. MP4: recordings, wiki | GIF (light, dark) ~37 s, ~0.5 MB · `plan-swarm-loop-stepper.html` · MP4 (light, dark) 1:56, 1920×1200, ~2.4 MB · PNG still |
| `terminal-replay/` | Replay of a real end-to-end run (`examples/e2e_demo.py`): real commands, real gate blocks, real approvals | Showing engineers what a session looks like | GIF, about 44 s, ~2 MB; PNG still |
| `explainer/` | Interactive, step-by-step page: 18 steps, 4 lanes (you, supervisor, roles, git), branch graph, and files written so far | Onboarding: a new team member clicks through at their own pace | Self-contained HTML; PNG previews |
| `cheatsheet/` | One-page poster: setup, running the swarm, calling a role, the loop, the six phrases, the rules, troubleshooting | Printing, pinning in a wiki, desk reference | SVG (light and dark); 3200×2080 PNG |

## Viewing

- **GIFs, PNGs, SVGs:** open them in a browser or image viewer, or embed them in Markdown, for example `![plan-swarm loop](images/lifecycle/plan-swarm-loop-light.gif)`.
- **Loop stepper:** open `lifecycle/plan-swarm-loop-stepper.html` in a browser (offline). Each click, →, Space, or presentation-clicker press plays the next stage's animation and then waits; a press during the animation finishes it.
  - Keys: ← back, 1–9 and 0 jump to stages 1–10, Home and End go to the intro and summary, N toggles the speaker notes, T toggles the theme, F goes full screen.
  - Autoplay (off by default) advances every 4, 7 or 10 s.
  - Deep links: `#stage=4`, `#t=dark`, `#notes=0`, for example `#stage=7&t=dark`. The address bar follows along, so you can bookmark a stage.
- **Loop MP4:** about 10 s per stage, so viewers can pause and scrub. GitHub shows MP4s only as uploaded attachments, not as repository files.
- **Explainer:** open `explainer/plan-swarm-explainer.html` in a browser. It needs no network access.
  - Keys: ← and → step, and Space plays and pauses. Buttons step, jump to the first or last step, and toggle the theme.
  - Deep links: `#step=7`, `#t=dark` or `#t=light`, and `#static=1` (no animation, used for the previews). They combine, for example `#step=7&t=dark`.

## Rebuilding

The builds use headless Chrome for screenshots, Pillow for the GIFs, and the ffmpeg binary bundled with `imageio-ffmpeg` for the MP4s. Both come through `uvx`, so nothing is installed globally. Set `CHROME` if Chrome is not at `/Applications/Google Chrome.app/...`.

```bash
uvx --with pillow --with imageio-ffmpeg python3 images/lifecycle/build.py   # loop.html → GIFs, stills, MP4s, stepper
uvx --with pillow python3 images/terminal-replay/build.py    # transcript → terminal.html → GIF + still
uvx --with pillow python3 images/cheatsheet/build.py         # writes SVGs, then renders PNGs
```

- `_build/gifkit.py` is the shared helper. It captures each frame from a URL fragment (`#f=N&t=dark`) at 2× scale, downsamples it, and writes every frame with one shared palette so the GIF does not flicker. `save_mp4` encodes the full 2× frames with per-frame durations.
- `lifecycle/build.py` holds the stage list, the speaker notes, and one `render(frame)` function. `loop.html` (which the GIF and MP4 screenshot) and the stepper are both generated from it, so the three forms cannot drift apart. GIF timing is in `frames()`; MP4 timing is in `VIDEO_DUR`.
- `terminal-replay/build.py` reads `/tmp/swarm-e2e/transcript.json`, or a path passed as the first argument. If the file is missing, it runs `examples/e2e_demo.py` to regenerate it.
- The explainer is hand-written HTML. Edit it directly; to refresh its previews, screenshot the page with `&static=1` added, in both themes.

## Accuracy

Phrases, branch names (`swarm/{m}`, `swarm-wip/{m}/{task}`), stages, and gate behavior follow `plugins/plan/README.md` and `topology.md`. When those change, rebuild the artifacts (AGENTS.md, invariant 9).

- The terminal replay's commands and outputs come from a real run.
- The narration captions in the replay are illustrative.

## Legacy

`plan_lifecycle_light.gif` and `plan_lifecycle_dark.gif` are the 2.1 animations. They predate the 3.0 gates, phrases, and stages, and no document references them. They are kept until someone decides to remove them.
