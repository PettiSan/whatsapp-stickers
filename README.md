# whatsapp-stickers

A folder of raw photos goes in. A published WhatsApp sticker pack comes out. A human approves the
preview and says the word that publishes; everything in between is automated.

Built for a WhatsApp group that trades NFL stickers. Three parts:

1. **`make_stickers.py`, the image pipeline.** Drop 3 to 30 photos into a folder (`jpg`, `jpeg`,
   `png`, `webp` or `avif`, any size), run one command, get 512x512 transparent-background stickers
   plus a `report.json` with everything the publishing form asks for. No manual background removal,
   no resizing, no renaming.
2. **An agent procedure**, in `CLAUDE.md` and two slash commands, `/processa` and `/publica`. Claude
   Code runs the script, reports what it changed in each photo, and then drives the user's real
   Chrome to fill the publishing form, upload the stickers and verify the result. It stops before the
   Publish button.
3. **A human**, who approves the preview and, later, gives the order to publish.

The interesting part is not the stickers. It is what the pipeline decides on its own, what it refuses
to decide, and where the line between the agent and the human sits.

---

## Publishing: the agent fills the form, the human clicks Publish

The packs live on getstickerpack.com. Its editor is a web form: title, description, up to 20
keywords, a color, an icon, a cover image and a grid of 30 sticker slots with a batch upload. Once the
script has run, filling that form is all the manual work that is left, and the site makes it worse:
**nothing is saved until you publish.** Close the tab and the form is gone.

`/publica <pack>` in Claude Code does the filling. It reads `out/report.json`, which the script
already wrote with the pack name, description, keywords, color and the absolute path of every sticker
in order, and then:

1. Opens the dashboard in the **user's own Chrome**, through the Claude in Chrome extension, already
   logged in. It is the only tool available here that can put a file into a file input; the embedded
   browser cannot. Login is the human's job: the agent never types a password.
2. Reuses an empty draft if the account has one, otherwise creates a new pack.
3. Fills title, description and color by element id. Keywords go through the site's tag widget, which
   has rules of its own (below).
4. Uploads the icon and the cover, then every sticker in a single batch call, in order.
5. Verifies through the page's own JavaScript (`getCurrentStickersCount()`, the in-memory
   `stickerPackUpdate.metadata`) and through the network log: every upload `POST` came back 200.
6. Takes a screenshot of the grid and **stops, with the tab open.**

The human looks at the screenshot and types "publica". Only then does the agent click *Publish
stickerpack* and *Confirm & publish*. The site reviews the pack and releases a URL; that URL goes into
`Stickers.md`, committed together with the pack's raw photos, and only then does the pack count as
done.

Rules that do not change, written into the procedure:

- **Never click Publish or Confirm without an explicit order in the conversation.** Mapping, filling,
  uploading and showing a screenshot: yes. Publishing: only on command.
- **Never type a password anywhere**, even if offered.
- **Everything happens in one tab, with no reload and no navigation**, because of how the site works.

### How the site was mapped

Rather than clicking around, I read the editor's own script (`js/edit-sticker-pack.js`, 2026-09-13).
What it showed:

- **Nothing persists before Publish.** Text fields only update an object in memory. Icon, cover and
  stickers are uploaded to S3 the moment each file input changes, but their association with the pack
  also lives only in memory: `publish-stickerpack` sends the whole object at once. The account's
  "draft" is just an id; reopen it and the form is empty. Hence one tab, no reload.
- There is no Save button. Publish requires at least 3 stickers and opens a terms modal.
- The grid has 30 slots. Batch upload distributes files, in order, into the first empty slots, and
  warns when the pack is full.
- The icon is stored as uploaded and displayed at 189 px; the site generates the 96x96 WhatsApp tray
  by itself. So the 512 goes up, never the `tray.png`.
- The keyword widget lowercases everything, commits a tag on comma, and updates its model on blur,
  reading it **before** the pending term is committed. A term without a trailing comma shows up as a
  tag and is silently missing from the model. Removing a tag with × does not update the model either.
  And the element that carries the id sits off screen; the input that actually takes focus is a
  sibling, so the agent focuses it through JavaScript and checks `document.activeElement` before
  typing. Found on the second pack, 2026-09-14.

Mapped on 2026-09-13 with an 8-sticker test pack. Reconfirmed on 2026-09-14 with a 25-sticker pack.

### Which model, which session

The upload runs in a **fresh session, on Sonnet, with no subagent.** Three deliberate choices:

- **Sonnet.** The recipe is mapped down to element ids, so this step is execution, not reasoning.
  What protects against clicking the wrong button is the rule above, not the size of the model. Opus
  driving a browser is expensive for nothing.
- **No subagent.** The flow has a mandatory stop in the middle, where the human looks at a screenshot
  and says "publica". A subagent cannot receive that mid-flight, its report does not reach the user
  directly, and it would be driving the real browser, which is exactly where the human needs to be
  able to interrupt.
- **Fresh session.** Screenshots and page reads fill a context window fast, and the model is chosen
  per session.

---

## What happens to each photo

A PNG that already has a transparent background (a logo pulled off the web) skips everything and is
only reframed. Everything else goes through four steps.

**0. Manual crop**, if `pack.json` asks for one on that file. A photo with a manual crop skips step 1,
because the framing was already chosen by a human.

**1. Caption and text overlay removal.** RapidOCR finds text, and text at the top or bottom of the
frame is cropped off. The threshold is deliberate: it only counts as a caption if it has letters and
**two or more words**, or a single word covering **30% or more of the width**. A jersey number, a logo
acronym or a small watermark does not trigger a crop. A top crop never cuts into the person; a bottom
crop takes at most 40% of their height. Text in the middle of the photo is left alone, and the log
line says so, because that is a case where replacing the photo is cheaper than any heuristic.

**2. Background removal**, with `rembg` and `birefnet-general-lite`.

**3. Isolating the subject.** When there is more than one person, YOLO segments each of them and
anyone under **50% of the largest person's area** is erased. Two people of similar size both stay,
which is what you want for a celebration between teammates. If the largest person occupies less than
**5%** of the photo, the subject is not a person and nothing is touched.

**4.** Crop, then frame to 512x512 with a margin.

---

## Two decisions worth explaining

### Whatever the subject is holding comes with them

A ball, a trophy, a helmet, a microphone. This is not object detection. The cut **erases the pixels of
whoever was discarded** and keeps whatever stays attached to the subject, instead of cutting along the
subject's silhouette.

The difference shows up when a bystander is touching the subject, a reporter standing next to the
player: she is removed, the trophy in his hand stays. Before 2026-09-14 the cut followed the silhouette
and ate every object in the subject's hands.

### A loose ball in the air is a known gap, and it stays one

A ball that nobody is holding is attached to nothing, so keeping it would need detection. The `sports
ball` class from COCO is right there in the same YOLO model. It does not work here, and I have the
numbers:

| Case | Confidence |
|---|---|
| Ball in a player's hands | 0.73 and 0.96 |
| **Ball loose in the air** | **0.113** |
| Noise: a Pepsi logo on a background panel | 0.107 |
| Noise: a player's shoulder, in a photo where his real ball went undetected | 0.113 |

Measured on one pack, 2026-09-14. COCO was trained on round balls and reads an oval one badly, so
signal and noise overlap. Any threshold low enough to catch the airborne ball also catches the
advertising board behind it. The threshold stays at 0.5 and **the loose ball is genuinely lost.**

That is the only known gap. Closing it would mean training a detector, which is only worth it if it
turns out to matter across many packs. Until then it is written down rather than papered over, and
there is a manual escape hatch below.

---

## Where each rule lives

Three kinds of rule, three places. Putting one in the wrong place is what makes rules rot.

| Kind | Lives in | Example |
|---|---|---|
| Generic perception | the models, off the shelf | people and balls (YOLO), text (RapidOCR), foreground (BiRefNet) |
| Policy that applies to every photo | `make_stickers.py` | keep what the subject is holding, drop bystanders, crop captions |
| Taste, per photo | `pack.json`, under `photos` | "just Macdonald's face in `mike-3`" |
| The saved prompt | `.claude/commands/` | the boilerplate behind `/processa` and `/publica` |

Two consequences.

**No model gets trained for objects in hand.** A held ball or trophy needs no detector: it is attached
to the subject, and the connectivity rule already covers it. Training would be expensive on the wrong
axis. The bottleneck is not GPU (there is an RTX 5060 Ti in this machine); it is labeling, because the
pipeline consumes segmentation masks, not boxes, so it would mean drawing polygons by hand on hundreds
of photos. The one measured exception, the loose ball, is above. If it starts showing up in many
packs, training becomes the honest answer. With one or two photos per pack, it is not.

**No per-photo request lives in prose.** Not in the chat, not in a `.md`. Prose needs a human to
reread it and reapply it on every run, and that is exactly what gets lost. It goes into `pack.json`,
where the same command gives the same result six months from now.

---

## Adjusting one photo by hand

Anything that is **taste rather than perception** goes into `pack.json`, under `photos`. The key is the
filename without its extension, and every rectangle is `[x1, y1, x2, y2]` as a **fraction of the
original image**:

```json
"photos": {
  "mike-3": { "crop": [0.42, 0.23, 0.74, 0.50] },
  "kupp-2": { "keep": [[0.30, 0.08, 0.45, 0.19]] },
  "mike-2": { "drop": [[0.0, 0.58, 0.33, 1.0]] }
}
```

| Key | What it does | When |
|---|---|---|
| `crop` | crops to that rectangle before anything else, and skips the caption search | "just the face", "cut from the waist down" |
| `keep` | re-runs background removal **inside that rectangle only** and forces whatever comes out into the result | the pipeline lost something: a ball in the air, an object the model read as background |
| `drop` | erases the rectangle at the end | leftover mess: a piece of a person YOLO never detected, so there was no mask to subtract |

**Why `keep` works:** inside a tight rectangle around the object, that object is the salient one. The
same model that got it wrong on the full photo gets it right in there. That is the escape hatch for the
loose ball that detection cannot cover. If the model finds no edge at all inside the rectangle and
hands back more than 65% of it, the box itself is used, rounded to an ellipse: `keep` is the human
asserting that something is there.

To find a rectangle, crop a test file and **look** before writing the numbers down. A coordinate grid
over the enlarged photo makes the fraction readable directly. Guessing coordinates is not an option.

---

## Measured

Eight test images, CPU, 2026-09-13:

| Model | Per image |
|---|---|
| `isnet-general-use` | ~1.3 s |
| `birefnet-general-lite` (default) | ~7 s |
| `birefnet-general` | ~13 s |

YOLO and OCR add roughly 0.5 s per image. A 30-image pack on defaults takes about four minutes,
unattended.

**YOLO runs in a separate process on purpose.** After a torch inference in the same process, `rembg`
(onnxruntime) drops from ~6 s to ~12 s per image and never recovers. Measured, cause not investigated,
isolating it fixed it. I would rather write that down than pretend I know why.

---

## Published

Two packs have gone through the whole flow, script to browser to public URL:

| Pack | Source photos in `packs/` | Published |
|---|---|---|
| [Seattle Seahawks](https://getstickerpack.com/stickers/garrettmvp-seattle-seahawks-2026) | 25 | 2026-09-14 |
| [Denver Broncos](https://getstickerpack.com/stickers/garrettmvp-denver-broncos-2026) | 29 | 2026-09-14 |

The first commit in this repository is from 2026-09-13. The Seahawks pack was published the next day.

`Stickers.md` is the full index, by NFL division. The other 18 packs in it are from 2025 and were made
by hand, one photo at a time, before this repository existed. They are the reason it exists.

---

## Using it

### Setup, once

```
setup.cmd
```

Creates `.venv/` with the `py` launcher (Python 3.14) and installs `rembg`, `ultralytics` and
`rapidocr`. A few minutes and about 2 GB of packages; torch CPU alone is ~1 GB. Models (~250 MB)
download on first use into `%USERPROFILE%\.rembg\`. All of that is local and gitignored. What the
repository carries is the code and the raw photos of each pack, a few MB per pack.

The wrappers are Windows `.cmd` files; the script itself is plain Python.

### Making a pack

1. Create `packs/<pack-name>/` and drop the raw photos in. `jpg`, `jpeg`, `png`, `webp` and `avif`,
   any size; below 300 px the script warns it will look blurry. One of them must be named `logo.*`:
   it becomes the pack icon and cover. Between 3 and 30 images.
2. Copy `pack.template.json` in as `pack.json` and fill three fields:
   ```json
   { "name": "Dallas Cowboys", "keywords": ["cowboys", "dak prescott"], "color": "#041E42" }
   ```
   The name template, the description and the fixed hashtag come from `defaults.json`. If a template
   placeholder is left in, the script says so.
3. Open Claude Code in the clone folder (not in a worktree: the `.venv/` and any uncommitted pack
   folder are not there) and run `/processa dallas-cowboys`. The agent runs the script, sends back
   `preview.png` and lists the warnings: a photo to swap, a missing field. Approve, or swap photos
   and run it again.
4. In a fresh session, `/publica dallas-cowboys`. The form gets filled and the agent stops before
   Publish, screenshot on screen. Say "publica".
5. When the URL shows up in the dashboard, register it: the agent puts it in `Stickers.md` and
   commits the pack folder, raw photos and `pack.json`, together with the index.

Without the agent: steps 1 and 2 are the same, then `stickers.cmd dallas-cowboys`, look at
`out/preview.png` and `out/log.txt`, and fill the site's form by hand from `out/report.json`.

The script logs in Portuguese. Each line says what was done to that photo: `texto cortado: base 25%`
(caption cropped, bottom 25%), `pessoas: 10 -> 1` (people found and kept), `objeto junto` (a held
object survived the cut), `bola: 1` (a ball forced back in), `crop do pack.json`.

### What it writes

Into `packs/<pack>/out/`, gitignored:

| File | What it is |
|---|---|
| `stickers/01-<name>.png … NN-<name>.png` | 512x512, transparent background: what goes into the batch upload |
| `tray.png` | 96x96 icon, WhatsApp spec; not uploaded, the site wants the 512 and makes its own 96 |
| `preview.png` | contact sheet, original next to result, to check before uploading |
| `log.txt` | per-image decisions, with an `AVISOS` (warnings) section at the end |
| `report.json` | everything the upload needs, already assembled: site fields, cover, icon, every sticker path in order, warnings |
| `webp/` | only with `--webp`: WebP under 100 KB, WhatsApp's native format |

Exit codes: `0` clean, `3` produced everything but there are warnings, `2` did not run. Exit 3 is not
a failure; it is the list of things a human has to decide.

A bad result is usually cheaper to fix by swapping the source photo than by any flag.

### Options

| Flag | Effect |
|---|---|
| `--outline 8` | white 8 px outline (default 0) |
| `--margin 16` | transparent margin around the sticker |
| `--model X` | `birefnet-general-lite` (default), `isnet-general-use` (5x faster, worse with people in the background), `birefnet-general` (2x slower than lite, marginal gain) |
| `--keep-text` | do not crop captions |
| `--keep-all` | do not discard secondary people |
| `--force-bg` | treat a transparent PNG as a normal photo |
| `--tray josh` | pick which image becomes the icon (substring of the filename; default `logo`) |
| `--webp` | also emit `out/webp/` |
| `--out dir` | write somewhere else |

### Environment

Python 3.14; rembg 2.0.84, onnxruntime 1.30 CPU, Pillow 12.3, ultralytics 8.4 with torch 2.14 CPU,
rapidocr 3.9. Torch comes in transitively through `ultralytics`, and on Windows the default PyPI wheel
is the CPU build, which is why `setup.cmd` does not install it separately. If a CUDA build (~3 GB) ever
shows up by default, install the CPU one first from `download.pytorch.org/whl/cpu`.

---

## WhatsApp sticker spec

From `github.com/WhatsApp/stickers`, `Android/README.md`: 512x512, WebP, static under 100 KB, animated
under 500 KB, 96x96 PNG tray icon under 50 KB, 3 to 30 stickers per pack, an 8 px white outline
recommended. The publishing site accepts PNG and converts to WebP itself.

---

## The rest

`CLAUDE.md` is the agent procedure: how to run and report a pack, the mapped upload form, the rules
that never bend. `.claude/commands/` holds the two slash commands. `Stickers.md` is the index of
published packs, versioned here as the single source of truth. The procedure, the commands and the
script's log are in Portuguese, the language the group runs in; this README is the English entry
point.

MIT licensed. The photos under `packs/` belong to their respective owners and are there as pipeline
input, not as redistributable assets.
