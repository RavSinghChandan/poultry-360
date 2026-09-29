
## Feature 3 — Count the flock (`count`)

Photograph the shed; the app proposes a count, draws boxes so it can be
checked by eye, and asks the farmer to confirm or correct it.

**It does not claim to be exact, and cannot be.** Birds stand behind each
other, face away and leave the frame. On a dense barn photo the same image
honestly yields 9 birds at one confidence threshold and 17 at another. Under
rule 5 of the feature contract, the *recorded* flock size is the farmer's
confirmed number; the model only proposes it.

| Endpoint | Purpose |
|---|---|
| `GET /api/count/tips` | How to take a photo that counts well |
| `POST /api/count/photo` | Propose a count with boxes and a quality flag |
| `POST /api/count/confirm` | Record the farmer's figure and the model's error |

Quality is `high`, `medium`, `low` or `none`, from two signals: how many
detections were uncertain, and how crowded the birds are. Crowding predicts
birds missed entirely — but only counts against quality once there are enough
birds for occlusion to plausibly hide one, since three hens filling a frame
overlap completely and are still counted correctly.

Model: YOLO11n (COCO class 14 "bird"), Ultralytics, AGPL-3.0. Runs on CPU via
onnxruntime in roughly 40 ms per photo.

### Video

`POST /api/count/video` counts across a clip of up to 75 seconds.

Video beats a photo because a bird hidden behind another in one frame is
visible in the next. On the same flock a single photo found 13 birds and a
three-second pan found 19.

It also introduces a failure a photo cannot have. Counting each frame and
adding them up gives 333 birds for a flock of about 25, because the same bird
is counted in every frame it appears in. Detections are therefore matched
across sampled frames by box overlap, and the count is the number of distinct
tracks seen in at least two frames.

Two things break tracking, and both are detected and reported rather than
hidden:

* **Fast camera movement** — birds move too far between samples to be matched.
* **Cuts between separate views** — nothing on screen after the cut is the
  same bird as before it, so totals from either side cannot be combined.

Frames are compared directly as small greyscale thumbnails to find cuts; track
bookkeeping alone cannot see them, because within each shot the tracker
matches perfectly. A video with two or more cuts is reported as `motion:
"fast"`, `quality: "low"`, and the farmer is told plainly that the total is
not reliable.

## Languages

Bengali is the default. Hindi, Bhojpuri, Maithili and English are also
available, and the farmer picks from a control in the header. The choice is
kept in the browser, so it is chosen once.

`core/languages.py` holds the list. A `Text` is a map from language code to
string; features write one and the platform resolves it at the edge, so
adding a language is adding entries to a dict rather than editing every
feature.

Each language declares a fallback, and a missing string walks that chain
rather than showing a blank. Bhojpuri and Maithili fall back to Hindi rather
than English, because a speaker of either reads Hindi far more easily. Every
chain ends at English, which every string must have.

`GET /api/languages` lists them. `GET /api/features?lang=bn` returns menu
labels already translated, and every count endpoint takes a `lang` field and
returns its note, quality label, tips and errors in that language.

The older `name_en` / `name_hi` fields are still served, so a client that has
not been updated keeps working.
