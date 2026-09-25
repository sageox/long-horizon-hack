# FLUX 3 Action on the 17:30 roast (F6)

The planner's `take_roast_out` becomes FLUX 3 Action's instruction. We run the
policy once on a rented GPU, keep what it predicts, and show it after the task
board's 17:30 decision.

## What we get, and what we don't

FLUX 3 Action is a 7B robot policy. Camera frames, joint state and an
instruction go in; one plan comes out: 32 steps of seven joint targets in
radians plus a gripper fraction, `actions.npy` with shape `(1, 32, 8)`, about
2.1 s of motion at 15 Hz on the DROID Franka arm.

**There is no video to play.** The released model samples video tokens with
the actions but does not decode them ("Video tokens are sampled jointly with
actions but are not decoded", `docs/setup.md` in the repo). What we can show
is the 32-step joint plan beside the three camera frames it planned from.
Those frames come from a public DROID lab episode, not a kitchen, so say so.
Never play a FLUX 3 Video clip as if the policy produced it.

## Needs

- Linux, Python 3.12, an NVIDIA GPU with about 32 GB free for BF16
  inference (L40S, A100, H100, H200; not a 24 GB card). Reference stack:
  PyTorch 2.10, CUDA 12.8. One plan takes 79 ms on an H200.
- `ffmpeg`, `uv`, a Hugging Face account (`hf auth login`).
- About 800 MB for the DROID sample, plus the checkpoint.

## Commands

Verbatim from [the inference guide](https://docs.bfl.ai/flux_3/flux3_action_inference)
and the repo's `docs/prepare.md`.

```sh
git clone https://github.com/black-forest-labs/flux-action.git
cd flux-action
uv sync --locked --extra encoders --extra data
uv pip install --python .venv/bin/python 'natten==0.21.6+torch2100cu128' \
  --find-links https://whl.natten.org/
ffmpeg -version

uv run hf auth login
uv run hf download black-forest-labs/flux-3-action-droid \
  --revision ea77cad51fd6e919b2aeb891ae9113828be5698a \
  --exclude 'variants/*' --local-dir outputs/droid

uv run hf download nvidia/Cosmos3-DROID --repo-type dataset \
  --revision 5c11a20accb11497270a5247a7f1e66ad04c956c \
  --local-dir outputs/public-droid/source \
  --include success/meta/info.json \
  --include success/meta/tasks.parquet \
  --include success/meta/episodes/chunk-000/file-000.parquet \
  --include success/data/chunk-000/file-000.parquet \
  --include success/videos/observation.image.wrist_image_left/chunk-000/file-000.mp4 \
  --include success/videos/observation.image.exterior_image_1_left/chunk-000/file-000.mp4 \
  --include success/videos/observation.image.exterior_image_2_left/chunk-000/file-000.mp4
uv run hf download KarlP/droid keep_ranges_1_0_1.json --repo-type model \
  --revision bcb840c3b496533e0adf548a54b51f2f00057837 \
  --local-dir outputs/public-droid/source
uv run flux-action prepare-droid --source-root outputs/public-droid/source \
  --lock configs/droid/public_sample.lock.json --episode-index 0 \
  --output outputs/public-droid/episode-000000
uv run python examples/droid/make_observation.py outputs/public-droid/episode-000000 \
  --seed 0 --output outputs/public-droid/observation.npz
```

First with the episode's own caption, to prove the setup:

```sh
task_caption=$(uv run python -c 'import json; print(json.load(open("outputs/public-droid/observation.json"))["task"])')
uv run flux-action infer --checkpoint outputs/droid \
  --observation outputs/public-droid/observation.npz --task "$task_caption" \
  --output outputs/droid/inference-run
```

Then with ours:

```sh
uv run flux-action infer --checkpoint outputs/droid \
  --observation outputs/public-droid/observation.npz \
  --task "take the roast chicken out of the oven and put it on the counter" \
  --output outputs/droid/roast
```

## Record

Copy `outputs/droid/roast/` (actions and report) and
`outputs/public-droid/observation.npz` back into this repo under `flux/`, then
plot the plan and the frames it saw:

```sh
uv run --with numpy --with matplotlib python - <<'EOF'
import numpy as np, matplotlib.pyplot as plt
a = np.load("flux/roast/actions.npy")[0]            # (32, 8)
fig, ax = plt.subplots(figsize=(8, 3))
for j in range(7):
    ax.plot(a[:, j], label=f"joint {j + 1}")
ax.plot(a[:, 7], "k--", label="gripper")
ax.set_xlabel("step (15 Hz)"); ax.set_ylabel("radians / closed fraction")
ax.set_title("FLUX 3 Action: take the roast chicken out of the oven")
ax.legend(fontsize=7, ncol=4); fig.tight_layout(); fig.savefig("flux/roast/plan.png", dpi=160)
obs = np.load("flux/observation.npz")
print(obs.files)  # find the image array, then save it as flux/roast/frames.png
EOF
```

## On stage

After the task board's `take_roast_out` at 17:30: "FLUX 3 Action can take the
roast out of the oven. It can't remember there's a roast in the oven." Show
`plan.png` and `frames.png`, and say plainly that this is a plan from a public
lab observation, not a rollout on a robot. With no GPU by 15:30, cut FLUX: it
is first in the plan's cut order.
