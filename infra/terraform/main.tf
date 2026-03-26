locals {
  lb_domain = var.lb_domain != "" ? var.lb_domain : "${google_compute_global_address.lb.address}.nip.io"
}

data "google_project" "current" {
  project_id = var.project_id
}

data "google_secret_manager_secret" "gemini_api_key" {
  secret_id = var.gemini_api_key_secret_name
}

resource "google_project_service" "required_apis" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "iap.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "cloudscheduler.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "containers" {
  depends_on = [google_project_service.required_apis]

  location      = var.region
  repository_id = "rag-filesearch"
  description   = "Container repo for Intelligent Document Q&A."
  format        = "DOCKER"
}

resource "google_storage_bucket" "rag_docs" {
  depends_on = [google_project_service.required_apis]

  name                        = var.gcs_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
}

resource "google_service_account" "web" {
  depends_on = [google_project_service.required_apis]

  account_id   = "rag-web-sa"
  display_name = "RAG web service account"
}

resource "google_service_account" "job" {
  depends_on = [google_project_service.required_apis]

  account_id   = "rag-job-sa"
  display_name = "RAG sync job service account"
}

resource "google_service_account" "scheduler" {
  depends_on = [google_project_service.required_apis]

  account_id   = "rag-scheduler-sa"
  display_name = "RAG scheduler invoker service account"
}

resource "google_storage_bucket_iam_member" "job_object_viewer" {
  bucket = google_storage_bucket.rag_docs.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.job.email}"
}

resource "google_storage_bucket_iam_member" "job_object_admin" {
  bucket = google_storage_bucket.rag_docs.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.job.email}"
}

resource "google_project_iam_member" "scheduler_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_secret_manager_secret_iam_member" "web_secret_access" {
  secret_id = data.google_secret_manager_secret.gemini_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.web.email}"
}

resource "google_secret_manager_secret_iam_member" "job_secret_access" {
  secret_id = data.google_secret_manager_secret.gemini_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.job.email}"
}

resource "google_cloud_run_v2_service" "web" {
  depends_on = [google_project_service.required_apis]

  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = google_service_account.web.email

    containers {
      image = var.web_image

      ports {
        container_port = 8080
      }

      env {
        name  = "FILE_SEARCH_STORE_DISPLAY_NAME"
        value = var.file_search_store_display_name
      }

      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = data.google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_job" "sync" {
  depends_on = [google_project_service.required_apis]

  name     = var.job_name
  location = var.region

  template {
    template {
      service_account = google_service_account.job.email
      timeout         = "1800s"
      max_retries     = 1

      containers {
        image = var.job_image

        env {
          name  = "GCS_BUCKET_NAME"
          value = google_storage_bucket.rag_docs.name
        }

        env {
          name  = "FILE_SEARCH_STORE_DISPLAY_NAME"
          value = var.file_search_store_display_name
        }

        env {
          name = "GEMINI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = data.google_secret_manager_secret.gemini_api_key.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }
}

resource "google_cloud_scheduler_job" "sync_schedule" {
  depends_on = [google_project_service.required_apis]

  name      = var.scheduler_job_name
  region    = var.scheduler_region
  schedule  = var.scheduler_cron
  time_zone = "Asia/Kolkata"

  http_target {
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.sync.name}:run"
    http_method = "POST"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }
}

resource "google_compute_global_address" "lb" {
  depends_on = [google_project_service.required_apis]

  name = "rag-web-lb-ip"
}

resource "google_compute_region_network_endpoint_group" "web_neg" {
  depends_on = [google_project_service.required_apis]

  name                  = "rag-web-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.web.name
  }
}

resource "google_compute_backend_service" "web_backend" {
  depends_on = [google_project_service.required_apis]

  name                  = "rag-web-backend"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.web_neg.id
  }

  dynamic "iap" {
    for_each = var.enable_iap ? [1] : []
    content {
      oauth2_client_id     = var.iap_oauth_client_id
      oauth2_client_secret = var.iap_oauth_client_secret
    }
  }
}

resource "google_compute_managed_ssl_certificate" "web_cert" {
  depends_on = [google_project_service.required_apis]

  name = "rag-web-cert"
  managed {
    domains = [local.lb_domain]
  }
}

resource "google_compute_url_map" "web" {
  depends_on = [google_project_service.required_apis]

  name            = "rag-web-url-map"
  default_service = google_compute_backend_service.web_backend.id
}

resource "google_compute_target_https_proxy" "web" {
  depends_on = [google_project_service.required_apis]

  name             = "rag-web-https-proxy"
  url_map          = google_compute_url_map.web.id
  ssl_certificates = [google_compute_managed_ssl_certificate.web_cert.id]
}

resource "google_compute_global_forwarding_rule" "web_https" {
  depends_on = [google_project_service.required_apis]

  name                  = "rag-web-https-rule"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.lb.id
  target                = google_compute_target_https_proxy.web.id
  port_range            = "443"
}

resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  count = var.enable_iap ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.web.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-iap.iam.gserviceaccount.com"
}

resource "google_iap_web_backend_service_iam_member" "accessors" {
  for_each = var.enable_iap ? toset(var.iap_access_members) : toset([])

  project             = var.project_id
  web_backend_service = google_compute_backend_service.web_backend.name
  role                = "roles/iap.httpsResourceAccessor"
  member              = each.value
}
