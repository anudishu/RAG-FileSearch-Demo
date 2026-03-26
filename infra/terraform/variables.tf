variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Primary region for Cloud Run, Scheduler, and bucket."
  type        = string
  default     = "asia-south2"
}

variable "gcs_bucket_name" {
  description = "GCS bucket for source documents and .sync_state.json used by Cloud Run Job."
  type        = string
  default     = "lyfedge-rag-sync-bucket"
}

variable "file_search_store_display_name" {
  description = "Shared Gemini File Search display name used by BOTH service and job."
  type        = string
  default     = "Gemini File Search demo"
}

variable "gemini_api_key_secret_name" {
  description = "Secret Manager secret name that stores GEMINI_API_KEY."
  type        = string
  default     = "gemini-api-key"
}

variable "web_image" {
  description = "Container image for FastAPI web service."
  type        = string
}

variable "job_image" {
  description = "Container image for gcs-sync-job."
  type        = string
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "gemini-file-search-demo"
}

variable "job_name" {
  description = "Cloud Run job name."
  type        = string
  default     = "rag-gcs-file-search-sync"
}

variable "scheduler_job_name" {
  description = "Cloud Scheduler job name that triggers Cloud Run job."
  type        = string
  default     = "rag-gcs-file-search-sync-schedule"
}

variable "scheduler_cron" {
  description = "Cron schedule for Cloud Scheduler."
  type        = string
  default     = "0 */6 * * *"
}

variable "scheduler_region" {
  description = "Cloud Scheduler region (can differ from Cloud Run region)."
  type        = string
  default     = "asia-south1"
}

variable "lb_domain" {
  description = "Domain for HTTPS certificate. Leave empty to use <reserved-ip>.nip.io."
  type        = string
  default     = ""
}

variable "enable_iap" {
  description = "Enable IAP on the load balancer backend service."
  type        = bool
  default     = true
}

variable "iap_oauth_client_id" {
  description = "OAuth client ID for IAP (Web application type). Required when enable_iap=true."
  type        = string
  default     = ""
}

variable "iap_oauth_client_secret" {
  description = "OAuth client secret for IAP (Web application type). Required when enable_iap=true."
  type        = string
  sensitive   = true
  default     = ""
}

variable "iap_access_members" {
  description = "Members allowed to access the app through IAP."
  type        = list(string)
  default     = []
}
