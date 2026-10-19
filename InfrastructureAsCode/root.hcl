locals {
  app_vars     = read_terragrunt_config(find_in_parent_folders("app.hcl"))
  env_vars     = read_terragrunt_config(find_in_parent_folders("env.hcl"))
  project_vars = read_terragrunt_config(find_in_parent_folders("project.hcl"))
  region_vars  = read_terragrunt_config(find_in_parent_folders("region.hcl"))
}

generate "provider" {
  path      = "provider_google.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "google" {
  project = "${local.project_vars.locals.project_id}"
  region  = "${local.region_vars.locals.gcp_region}"
}
provider "google-beta" {
  project = "${local.project_vars.locals.project_id}"
  region  = "${local.region_vars.locals.gcp_region}"
}
EOF
}

generate "versions" {
  path      = "versions_override.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 5.0.0"
    }
  }
}
EOF
}

remote_state {
  backend = "gcs"
  config = {
    project                 = local.project_vars.locals.project_id
    location                = "us"
    bucket                  = "${local.app_vars.locals.app_id}-${local.env_vars.locals.environment}-tfstate-us"
    prefix                  = "${path_relative_to_include()}"
    skip_bucket_creation    = false
    skip_bucket_versioning  = false
  }
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}

inputs = merge(
  local.app_vars.locals,
  local.env_vars.locals,
  local.project_vars.locals,
  local.region_vars.locals,
)
