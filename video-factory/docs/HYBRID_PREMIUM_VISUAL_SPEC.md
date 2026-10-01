# Hybrid Premium — Visual Direction and Editorial Standard

Status: **selected by the user and mandatory**  
Format targets: vertical 9:16, 30-second and 60-second YouTube/Shorts masters.

## Non-negotiable definition

A generated 3–5 second Wan clip is a **master take**, not an edit duration. The
editor selects the strongest 0.3–3.0 second range and intercuts it with motivated
coverage. A scene is a narrative unit; a shot is one camera angle.

Rejected patterns:

- alternating one five-second image/clip with another;
- slideshow or Ken Burns zoom presented as AI motion;
- fixed shot duration or repeating transition templates;
- filler stock unrelated to the narration;
- using a full generated take only because it is available;
- decorative transitions without matched action, shape, direction, or meaning.

## Target visual density

| Master | Visual beats/cuts | Unique motion sources | Wan hero masters | Real/stock/archive | Graphics/composites |
|---|---:|---:|---:|---:|---:|
| 30 s | 20–30 | 12–18 | 4–6 | 6–10 | 2–4 |
| 60 s | 35–55 | 20–30 | 6–10 | 10–18 | 4–8 |

These are planning ranges, not quotas. The story and rhythm decide the final
count. Hook sections may use 0.3–0.9 second cuts; emotional hero moments may hold
for 2–4 seconds.

## Coverage grammar

For each important narrative scene, the Visual Director chooses a motivated
subset of:

1. establishing wide;
2. medium action/tracking;
3. close-up or reaction;
4. macro/insert detail;
5. POV or over-the-shoulder;
6. low/high angle;
7. environmental or consequence cutaway;
8. transition plate with compatible motion/shape.

Each shot specification must include:

- narrative purpose and exact timeline window;
- source class: Wan I2V/T2V, licensed real footage, stock, public domain, or graphics;
- framing, camera angle, lens character, camera movement, and subject action;
- lighting, palette, depth, motion direction, and continuity constraints;
- expected usable subrange and optional backup;
- cut-in/cut-out motivation, audio cue, and caption emphasis;
- source URL/license/attribution metadata when external footage is used.

## Editorial rhythm

- Cuts are motivated by action, meaning, gaze, geometry, narration, or sound.
- Prefer clean hard cuts; use match cuts, J/L cuts, sound bridges, masked cuts,
  whip transitions, and speed ramps only when source motion supports them.
- Change visual scale and perspective; never repeat the same medium framing for
  several consecutive shots.
- Reframe only genuine high-resolution moving footage. A zoom on a still does not
  satisfy the true-motion requirement.
- Music-beat cuts are selective. Narration comprehension and visual motivation
  take priority over cutting mechanically on every beat.

## Sound and captions

- Layer narration, music, room tone, ambience, Foley, impacts, risers, and
  transition sounds with intentional dynamic range.
- Use J/L audio edits and sound bridges to make visual cuts feel continuous.
- Duck music under narration and enforce final loudness/true-peak targets.
- Captions are word-aligned; animate phrases selectively and emphasize only
  semantically important words. Preserve mobile safe areas and visual hierarchy.

## Color and finish

1. normalize mixed sources;
2. match exposure, white balance, and contrast between adjacent shots;
3. apply a unified cinematic grade;
4. add restrained grain/bloom/halation/motion blur only when appropriate;
5. export a high-quality 1080×1920 master without an added watermark.

## Automated rejection gates

Reject or regenerate a shot when any mandatory gate fails:

- frozen/near-static motion where motion was requested;
- morphing identity, unstable face/body, duplicate subject, broken anatomy;
- unintended text/logo/watermark;
- first-frame I2V drift beyond the allowed identity/composition threshold;
- black frames, frame corruption, severe flicker, or cadence problems;
- mismatched motion direction or continuity with neighboring shots;
- no usable 0.3-second-or-longer edit range;
- low relevance to the narration;
- missing or unacceptable rights metadata for external media.

## Verified 15-second reference implementation

The mandatory executable reference is:

- plan: `examples/hybrid_premium/ancient_mystery/edit_plan.json`;
- renderer: `video_factory.hybrid_premium.renderer`;
- QA: `video_factory.hybrid_premium.qa`;
- master: `examples/hybrid_premium/ancient_mystery/sample_preview.mp4`.

Measured reference result: 15.00 seconds, 15 visual beats, six unique moving
sources, 1080×1920 at 30fps, H.264, stereo AAC, -14.2 LUFS, -1.5 dBFS true
peak, no full-black frame, and no very-low-motion run of 0.5 seconds or longer.
The renderer reproduced the Full HD master from the edit plan inside the project;
this is not a storyboard or a still-image zoom demo.

## Runtime planning assumptions (T4, unverified for final 5B profile)

- Cold Colab/model setup: about 4–10 minutes.
- Warm accepted Wan 5-second master: initially budget 6–12 minutes per attempt.
- Budget 1.0–1.7 attempts per accepted master; faces/complex action may need more.
- Hybrid Premium target: roughly 1.5–3.5 hours for 30 seconds and 3–6 hours for
  60 seconds, subject to actual T4 benchmarks and Colab quota.

The next benchmark must replace these estimates with measured Wan2.2 TI2V-5B
T2V/I2V data at 5 and 8 seconds before production scheduling is enabled.
