output "artifact_registry_repository" {
  description = "Artifact Registry repository for container images."
  value       = google_artifact_registry_repository.containers.id
}

output "documents_bucket" {
  description = "Documents bucket for ingestion + .sync_state.json."
  value       = google_storage_bucket.rag_docs.name
}

output "reserved_lb_ip" {
  description = "Global static IP used by HTTPS load balancer."
  value       = google_compute_global_address.lb.address
}

output "lb_domain" {
  description = "Domain configured for HTTPS certificate."
  value       = local.lb_domain
}

output "app_url" {
  description = "Application URL behind LB. Certificate issuance must complete first."
  value       = "https://${local.lb_domain}"
}

output "cloud_run_service" {
  description = "Cloud Run web service name."
  value       = google_cloud_run_v2_service.web.name
}

output "cloud_run_job" {
  description = "Cloud Run sync job name."
  value       = google_cloud_run_v2_job.sync.name
}

output "shared_file_search_store_display_name" {
  description = "Shared display name configured in BOTH Cloud Run service and job."
  value       = var.file_search_store_display_name
}
