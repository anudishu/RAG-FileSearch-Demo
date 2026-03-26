# Intelligent Document Q&A with Gemini File Search on Google Cloud

**Enterprise-ready RAG without building your own chunking, embedding, or vector database.**  
This repository is a **reference application** for teams that want **natural-language Q&A over their own documents**—upload files through a web UI, or land thousands of files in **Cloud Storage** and let a **Cloud Run Job** keep a **Gemini File Search** store in sync on a schedule. Users query the same knowledge base from the browser; **Google handles parsing, chunking, embeddings, indexing, and retrieval** behind the [Gemini File Search API](https://ai.google.dev/gemini-api/docs/file-search).

---

## Table of contents

1. [What this solution is for](#what-this-solution-is-for)
2. [Why not “classic” DIY RAG?](#why-not-classic-diy-rag)
3. [Why Gemini File Search](#why-gemini-file-search)
4. [How organizations typically use it](#how-organizations-typically-use-it)
5. [Architecture](#architecture)
6. [Repository layout](#repository-layout)
7. [Prerequisites](#prerequisites)
8. [Clone this repository](#clone-this-repository)
9. [Deploy step by step (Terraform)](#deploy-step-by-step-terraform)
10. [After deployment](#after-deployment)
11. [Configuration highlights](#configuration-highlights)
12. [Troubleshooting](#troubleshooting)
13. [Security and secrets](#security-and-secrets)
14. [Local development](#local-development)

---

## What this solution is for

| Audience | Need | What you get |
|----------|------|----------------|
| **Product & engineering teams** | Demo or pilot **document Q&A** with minimal ML ops | FastAPI UI + API, same File Search store as batch sync |
| **Enterprises** | **Many PDFs/DOCX** produced by pipelines, not by hand | **GCS** as the landing zone; **Cloud Run Job** ingests into File Search |
| **Platform teams** | Secure access behind **Google Cloud** networking | Optional **HTTPS Load Balancer** + **IAP** pattern (as in Terraform) |

If your goal is “users ask questions; answers should come from **our** documents,” this repo shows one complete path on GCP.

---

## Why not “classic” DIY RAG?

A typical custom RAG stack forces you to own:

1. **Parsing & layout** — PDFs, Office, scans.
2. **Chunking** — overlap, token limits, metadata.
3. **Embeddings** — model choice, batching, versioning.
4. **Vector database** — provisioning, scaling, backups, access control.
5. **Retrieval** — similarity search, re-ranking, prompt assembly.

That is a lot of **custom logic and operational burden**. This project **does not replace** those components with more code—it **delegates** indexing and retrieval to **Gemini File Search**, so your code focuses on **where files come from** (UI, GCS, pipelines) and **how users query** (FastAPI + Gemini tool calling).

---

## Why Gemini File Search

- **Managed RAG pipeline** — Upload or import documents into a **File Search store**; Google performs chunking, embedding, and indexing suitable for retrieval-augmented generation.
- **Simple application model** — Your app passes the store to the model as a **tool**; the model retrieves relevant material when answering.
- **Fits “lots of files”** — Pair with **GCS + Cloud Run Job + Cloud Scheduler**: new or updated objects are synced incrementally (this repo’s job uses **MD5-based** `.sync_state.json` in the bucket).

**Isn’t that cool?** Your **data pipeline** (ETL, sync from SharePoint, Drive export jobs, SFTP drops, etc.) only needs to **put files into GCS** (or a path you control). The **same Cloud Run job** can run every **10 minutes** (or any cron) to **embed and index** into File Search, while end users only use the **Q&A app**.

---

## How organizations typically use it

1. **Canonical bucket** — `gs://YOUR_BUCKET/` holds PDF, DOCX, TXT, MD, CSV (see `gcs-sync-job/sync_job.py` for supported types).
2. **Ingestion** — Anything that can write to GCS works: **Cloud Composer**, **Dataflow**, **scheduled exports**, **CI artifacts**, **manual `gsutil`**, or connectors that sync **Google Drive / OneDrive / SharePoint** into GCS (those are **separate products**; this repo assumes files **arrive in GCS**—you plug your connector or pipeline in front).
3. **Scheduled indexing** — **Cloud Scheduler** triggers **Cloud Run Job** on a schedule (e.g. **every 10 minutes**: cron `*/10 * * * *`).
4. **Query** — Users open the **web app** (behind LB + IAP if you use Terraform) and ask questions; the app queries Gemini with **File Search** attached to the **same** store display name as the job.

**Important:** The **Cloud Run service** and **Cloud Run job** must share the same **`FILE_SEARCH_STORE_DISPLAY_NAME`** (and typically the same **Gemini API key** project context) so queries hit the same logical store. Terraform sets one variable for both.

---

## Architecture

End-to-end flow (conceptual):

- **Developers** → Git + **Terraform** (state in a dedicated GCS bucket) → **Artifact Registry** → **Cloud Run**.
- **Users** → **HTTPS Load Balancer** → (optional **IAP**) → **Cloud Run** web app → **Gemini** + **File Search**.
- **Scheduler** → **Cloud Run Job** → reads **GCS** → **`upload_to_file_search_store`** → **File Search store**.

![System architecture — Terraform & CI/CD, Cloud Run web app, GCS sync job, Gemini File Search](docs/architecture-gemini-filesearch-rag.png)

**What the diagram shows:** (1) **IaC & CI/CD** — developer → GitHub → Terraform (state in GCS) and GitHub Actions → Artifact Registry → deploy to Cloud Run. (2) **Runtime** — user → Load Balancer → IAP → Cloud Run (FastAPI / UI) → Gemini + File Search for Q&A. (3) **Ingestion** — documents land in **GCS** (users or data pipelines); **Cloud Scheduler** runs the **Cloud Run Job** (`gcs-sync-job`) on a schedule; the job syncs objects into the **managed File Search** store so queries stay aligned with bucket content.

> The Terraform in this repo implements **LB + IAP + Cloud Run service + Cloud Run job + Scheduler + GCS bucket + IAM**; naming and regions may differ from the diagram labels—adjust `infra/terraform` variables for your project.

---

## Repository layout

| Path | Purpose |
|------|---------|
| `main.py` | FastAPI app + embedded UI: `/health`, `/api/v1/upload`, `/api/v1/query`, `/api/v1/status` |
| `file_search_service.py` | File Search store lifecycle, uploads, queries |
| `config.py` | Environment-based configuration |
| `gcs-sync-job/` | Cloud Run **Job** image: GCS listing, diff, sync to File Search |
| `Dockerfile` | Web service container |
| `infra/terraform/` | **IaC**: Cloud Run service & job, GCS bucket, Scheduler, LB, IAP, IAM, Artifact Registry |

---

## Prerequisites

- **Google Cloud project** with billing enabled (as needed for APIs you enable).
- Tools: **`gcloud`**, **`gsutil`**, **`terraform`** (≥ 1.5).
- **Gemini API key** ([Google AI Studio](https://aistudio.google.com/apikey) or your approved channel).
- For Terraform deploy: ability to create **Secret Manager** secrets and **OAuth** credentials for **IAP** (if `enable_iap = true`).

---

## Clone this repository

```bash
git clone https://github.com/anudishu/RAG-FileSearch-Demo.git
cd RAG-FileSearch-Demo
```

---

## Deploy step by step (Terraform)

Replace project IDs, regions, and bucket names with **your** values. Defaults in Terraform often use `lyfedge-project` and `lyfedge-rag-sync-bucket` as **examples**—change them in `infra/terraform/terraform.tfvars` if you fork for another environment.

### Step 1 — Authenticate and set project

```bash
gcloud auth login
gcloud auth application-default login
export PROJECT_ID="your-project-id"
export REGION="asia-south2"   # example: align with your Cloud Run region
gcloud config set project "$PROJECT_ID"
```

### Step 2 — Terraform remote state bucket

Create a **dedicated bucket** for Terraform state (example name from this project: `rag-system-lyfedge-project`—use your own naming in production):

```bash
export TFSTATE_BUCKET="your-tfstate-bucket"
gsutil ls "gs://${TFSTATE_BUCKET}" >/dev/null 2>&1 || \
  gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${TFSTATE_BUCKET}"
```

### Step 3 — Store the Gemini API key in Secret Manager

```bash
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create gemini-api-key --data-file=- 2>/dev/null || \
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets versions add gemini-api-key --data-file=-
```

Never commit API keys or OAuth secrets to git.

### Step 4 — OAuth client for IAP (manual in Console)

1. Open **Google Cloud Console** → your project.
2. **Security → Identity-Aware Proxy** (or **APIs & Services → Credentials** for a Web client, per org policy).
3. Complete **OAuth consent screen** if prompted.
4. Create or select an OAuth **Web application** client used with IAP.
5. Copy **Client ID** and **Client secret** into `terraform.tfvars` (see below).

### Step 5 — Build and push container images

**Option A — Cloud Build** (no local Docker required):

```bash
export REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/rag-filesearch"
gcloud artifacts repositories create rag-filesearch \
  --repository-format=docker --location="$REGION" 2>/dev/null || true

gcloud builds submit --tag "${REPO}/gemini-file-search-demo:latest" .
gcloud builds submit --tag "${REPO}/rag-gcs-file-search-sync:latest" ./gcs-sync-job
```

**Option B — Local Docker** — build and push the same tags to Artifact Registry.

### Step 6 — Configure Terraform variables

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit **`terraform.tfvars`** (this file is **gitignored**—do not commit secrets):

| Variable | Purpose |
|----------|---------|
| `project_id`, `region` | GCP project and primary region |
| `web_image`, `job_image` | Full image URIs from Step 5 |
| `gemini_api_key_secret_name` | Usually `gemini-api-key` |
| `file_search_store_display_name` | **Same value** for web + job (shared store) |
| `iap_oauth_client_id`, `iap_oauth_client_secret` | From Step 4 (if IAP enabled) |
| `iap_access_members` | Who may access the app via IAP |
| `scheduler_cron` | Default is every 6 hours; use **`*/10 * * * *`** for every **10 minutes** |
| `scheduler_region` | Cloud Scheduler location (some regions cannot host Scheduler; default in code is `asia-south1`) |

### Step 7 — Initialize and apply Terraform

Backend uses GCS; pass an access token if your environment needs user credentials for the backend:

```bash
export GOOGLE_OAUTH_ACCESS_TOKEN="$(gcloud auth print-access-token)"
terraform init -reconfigure \
  -backend-config="bucket=${TFSTATE_BUCKET}" \
  -backend-config="prefix=rag-filesearch/terraform" \
  -backend-config="access_token=${GOOGLE_OAUTH_ACCESS_TOKEN}"

terraform plan
terraform apply
```

### Step 8 — Read outputs

```bash
terraform output app_url
terraform output reserved_lb_ip
terraform output lb_domain
terraform output shared_file_search_store_display_name
```

Open **`app_url`** in a browser (HTTPS). If IAP is on, sign in with an allowed account.

---

## After deployment

### Test the web UI

- Upload a small PDF or TXT via the UI.
- Ask a question whose answer appears only in that document.

### Test GCS → Job → same store

```bash
export BUCKET="lyfedge-rag-sync-bucket"   # or your bucket name from Terraform
gsutil cp ./sample.pdf "gs://${BUCKET}/"

gcloud run jobs execute rag-gcs-file-search-sync --region="$REGION" --wait
```

Then query from the app **without** uploading the same file in the UI—answers should reflect GCS-ingested content if the job succeeded.

### Run Cloud Scheduler on demand

```bash
# Scheduler region may differ from Cloud Run (see terraform.tfvars / variables.tf)
gcloud scheduler jobs run rag-gcs-file-search-sync-schedule --location=asia-south1
```

### Verify shared File Search store name

Both the Cloud Run **service** and **job** must expose the same `FILE_SEARCH_STORE_DISPLAY_NAME`. Confirm in Console or:

```bash
terraform state show google_cloud_run_v2_service.web
terraform state show google_cloud_run_v2_job.sync
```

---

## Configuration highlights

| Topic | Notes |
|-------|--------|
| **Same store for UI + job** | Set one `file_search_store_display_name` in Terraform; it is injected into both workloads. |
| **Schedule** | Adjust `scheduler_cron` (e.g. `*/10 * * * *` every 10 minutes). |
| **Bucket name** | Override `gcs_bucket_name` in Terraform if you do not use the default. |
| **IAP** | Set `enable_iap = false` only if you accept a different access pattern (not recommended for public internet). |

---

## Troubleshooting

| Symptom | What to check |
|---------|----------------|
| **503 / API key not configured** | Secret exists; Cloud Run service account has `secretAccessor` on the secret. |
| **Query ignores a new GCS file** | Job execution logs; `.sync_state.json` in bucket; file extension allowed in `sync_job.py`. |
| **Wrong resume / name mismatch** | **Filename ≠ indexed text**—ensure the document body contains the names/terms you query (e.g. “Abhishek”) or ask using phrases that appear in the file. |
| **HTTPS / certificate** | Managed cert `ACTIVE` in Console; use `https://` URL from Terraform output. |
| **Scheduler errors** | Scheduler **region** must be valid for Cloud Scheduler; it can differ from Cloud Run region. |

---

## Security and secrets

- **Never** commit `terraform.tfvars`, `.env`, or API keys.
- Add `terraform.tfvars` to `.gitignore` (already in this repo).
- Rotate **Gemini** and **OAuth** credentials if they were ever pasted in chat or logs.
- Prefer **least-privilege** IAM on the GCS bucket and Secret Manager.

---

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U -r requirements.txt
export GEMINI_API_KEY="your-api-key"
python main.py
```

Open **http://127.0.0.1:8080** (or the port printed in logs).

Requirements: **`google-genai>=1.49.0`** for File Search; **`fastapi>=0.115`** avoids common `anyio` conflicts.

---

## License and contributions

This repository is intended as a **reference implementation** for demos and pilots. Adapt naming, regions, and security controls to your organization’s standards.

---

**Summary:** Clone the repo, push images, configure Terraform with your project and secrets, apply, then use **either** interactive upload **or** GCS + scheduled jobs to keep **one** Gemini File Search store fresh—**without** maintaining your own vector database or embedding pipeline.
