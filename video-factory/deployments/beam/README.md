# Beam Cloud validation path

Beam is the current **test candidate**, not yet an accepted production provider.
It officially advertises $30 of credit refreshed every month, custom images,
persistent volumes, GPU functions, and authenticated HTTP endpoints. The
remaining gate is practical: a new account must be able to run GPU code without
adding a payment card or phone number.

## Safe validation order

### 1. Create the account — but do not add payment details

Open <https://platform.beam.cloud/> and sign in using email, GitHub, Google, or
GitLab. The public registration page currently shows no phone field. Confirm the
dashboard shows the monthly free credit, then create an API key under **Settings
→ API Keys**.

Stop if Beam requires a card or phone before GPU execution. Do not select a paid
upgrade merely to continue the test.

### 2. Keep the token outside the repository

```bash
export BEAM_TOKEN='...'
uv tool install beam-client
beam configure default --token "$BEAM_TOKEN"
```

`BEAM_TOKEN` must never be committed or put in a workflow file.

### 3. Run the minimal real-GPU test first

```bash
beam deploy deployments/beam/gpu_smoke.py:gpu_smoke
```

Use the endpoint URL printed by Beam:

```bash
export BEAM_ENDPOINT_URL='https://...'
python deployments/beam/call_endpoint.py --url "$BEAM_ENDPOINT_URL"
```

Success requires a JSON response containing `"ok": true`, a GPU name, VRAM,
and a checksum produced by an actual CUDA matrix multiplication. Also inspect
the Beam usage page: the charge should be only a few seconds and should be
subtracted from the free monthly credit.

### 4. Deploy Wan only after the GPU test passes

```bash
beam deploy deployments/beam/fastwan_api.py:generate_video
```

First T2V test (about one second, two denoising steps):

```bash
export BEAM_ENDPOINT_URL='https://...'
python deployments/beam/call_endpoint.py \
  --prompt 'cinematic close-up of a paper boat moving through rain water, natural motion' \
  --duration 1.1 --width 480 --height 832 --steps 2 --seed 42
```

First I2V test:

```bash
python deployments/beam/call_endpoint.py \
  --prompt 'the camera slowly pushes in as wind moves the scene naturally' \
  --image /path/to/input.png \
  --duration 1.1 --width 480 --height 832 --steps 2 --seed 42
```

The endpoint returns a temporary `output_url`, generation metadata, GPU model,
and peak allocated VRAM. Download the MP4 promptly; the validation URL expires
in 24 hours.

## Deliberate first-test limits

- Model: `FastVideo/FastWan2.2-TI2V-5B-FullAttn-Diffusers`
- Real T2V and I2V, not pan/zoom animation
- 24 fps
- 25–97 frames (about 1.04–4.04 seconds)
- Maximum pixel area: `480×832`
- 1–8 inference steps
- RTX 5090 preferred, then RTX 4090, then A10G
- Model cache stored in a Beam volume; no secret is embedded in code

Limits must not be raised until the first run records output quality, wall time,
peak VRAM, cold-start behavior, and the exact usage debit in the Beam dashboard.

## Acceptance checklist

Beam is accepted only if all of these pass:

1. No card and no phone are required for the account and GPU run.
2. The dashboard actually grants and later refreshes the advertised monthly
   credit (the official pricing page states $30/month; the first run can only
   prove the initial grant).
3. The GPU smoke endpoint runs remotely.
4. Wan downloads/loads successfully and the cache persists.
5. T2V and I2V both return playable MP4 files through the HTTP endpoint.
6. No watermark appears, motion is real, and the model license remains suitable.
7. Actual costs fit the planned number of shots.

If item 1 fails, abandon Beam rather than adding a payment method. The no-card
fallback remains Hugging Face ZeroGPU: it is smaller (5 GPU minutes/day for a
free account) and custom hosting requires a verified-email account older than
30 days, but those conditions are explicitly documented.
