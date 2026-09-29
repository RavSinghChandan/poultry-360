
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
