# Terraform Infrastructure

This folder provisions production-style GCP infrastructure for this solution:

- Artifact Registry (Docker images)
- Cloud Storage bucket for ingestion (`GCS_BUCKET_NAME`)
- Cloud Run service (web app)
- Cloud Run job (GCS sync job)
- Cloud Scheduler trigger for the job
- External HTTPS Load Balancer + Serverless NEG
- Cloud Armor policy
- IAP on LB backend
- IAM bindings and service accounts

## Important

Terraform uses an existing Secret Manager secret for `GEMINI_API_KEY`. Create that secret first (with at least one version) before running `terraform apply`.

## Quick usage

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars
terraform init
terraform plan
terraform apply
```

After `apply`, check outputs:

```bash
terraform output app_url
terraform output shared_file_search_store_display_name
```
