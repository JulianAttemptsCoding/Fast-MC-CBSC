# Google Vertex AI Runbook

## 1. Prerequisites

- Google Cloud project with billing enabled;
- Vertex AI, Artifact Registry, and Cloud Storage APIs enabled;
- service account with read access to input bucket, write access to output bucket, and Vertex custom-job permission;
- Docker and gcloud CLI locally;
- a region supporting the selected GPU.

Prices and accelerator availability vary by region and date. Confirm immediately before submission.

## 2. Build and push image

```bash
export PROJECT_ID='YOUR_PROJECT'
export REGION='us-central1'
export REPOSITORY='cbsc-zdc'
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/cbsc-zdc:v2-2"

gcloud auth configure-docker "${REGION}-docker.pkg.dev"
gcloud artifacts repositories create "$REPOSITORY" \
  --repository-format=docker \
  --location="$REGION" || true

docker build -t "$IMAGE" .
docker push "$IMAGE"
```

## 3. Arrange frozen inputs

Local layout before upload:

```text
vertex_input/
├── artifacts/
│   ├── data/
│   ├── geometry/
│   ├── splits.json
│   └── splits_assignments.npz
└── configs/
    └── frozen_full_0_300_seed20260723.yaml
```

Upload:

```bash
gcloud storage cp --recursive vertex_input gs://YOUR_BUCKET/cbsc/input/full_0_300_seed20260723
```

The frozen config’s local paths are rewritten inside the container to the downloaded artifacts. Scientific values and hashes are retained.

## 4. Submit

```bash
python vertex/submit_custom_job.py \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --staging-bucket gs://YOUR_BUCKET/cbsc/staging \
  --container-uri "$IMAGE" \
  --display-name cbsc-full-0-300-seed20260723 \
  --input-prefix gs://YOUR_BUCKET/cbsc/input/full_0_300_seed20260723 \
  --output-prefix gs://YOUR_BUCKET/cbsc/runs/full_0_300_seed20260723 \
  --config-relative configs/frozen_full_0_300_seed20260723.yaml \
  --machine-type n1-standard-8 \
  --accelerator-type NVIDIA_TESLA_T4 \
  --accelerator-count 1 \
  --service-account YOUR_SERVICE_ACCOUNT
```

A T4 is an example compatible with the user’s earlier compute plan, not a guaranteed optimal or currently available choice.

## 5. Cost and throughput QA

Before a full job:

1. run a 10–20 minute target-hardware pilot;
2. record examples/second and projected epoch duration;
3. set a budget alert;
4. use one GPU and one replica initially;
5. record poor DataLoader utilization as optimization evidence and investigate
   it before projecting larger-run cost;
6. checkpoint every epoch;
7. copy outputs to GCS at job completion;
8. inspect quota and region pricing before every batch of jobs.

These observations inform cost and implementation choices. They are not
progression permission: a result on one GPU type neither authorizes nor forbids
training on another backend.

## 6. Recovery

The container uploads the run directory after normal completion. If the VM is preempted before upload, intermediate artifacts may be lost. For long runs, either use non-preemptible resources or extend the trainer with periodic GCS checkpoint synchronization and test that behavior in a pilot.

Resume by staging the prior checkpoint and setting `training.resume_from` in a new frozen runtime config. A resume must use the same stage and compatible environment.
