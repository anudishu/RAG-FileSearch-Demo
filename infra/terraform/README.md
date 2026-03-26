# Terraform

Provisions the usual pieces: Artifact Registry repo, GCS bucket for docs, Cloud Run service + job, Scheduler, external HTTPS LB + NEG, IAP on the backend, service accounts and IAM bindings.

You need a Secret Manager secret for `GEMINI_API_KEY` **before** apply (name defaults to `gemini-api-key`).

```bash
cp terraform.tfvars.example terraform.tfvars
# edit — never commit this file

export GOOGLE_OAUTH_ACCESS_TOKEN="$(gcloud auth print-access-token)"
terraform init -reconfigure \
  -backend-config="bucket=YOUR_STATE_BUCKET" \
  -backend-config="prefix=rag-filesearch/terraform" \
  -backend-config="access_token=${GOOGLE_OAUTH_ACCESS_TOKEN}"

terraform apply
```

`terraform output` shows URL and shared `file_search_store_display_name`.

Empty the documents bucket (or enable bucket `force_destroy` in code) before `terraform destroy` if destroy fails on non-empty bucket.
