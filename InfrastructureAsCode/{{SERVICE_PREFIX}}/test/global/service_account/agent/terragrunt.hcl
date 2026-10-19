terraform {
  source = "tfr:///terraform-google-modules/service-accounts/google?version=4.1.1"
}

include "root" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  current_directory = replace(basename(get_terragrunt_dir()), "_", "-")
  project_vars      = read_terragrunt_config(find_in_parent_folders("project.hcl"))
  region_vars       = read_terragrunt_config(find_in_parent_folders("region.hcl"))
  env_vars          = read_terragrunt_config(find_in_parent_folders("env.hcl"))
  app_vars          = read_terragrunt_config(find_in_parent_folders("app.hcl"))
}

inputs = {
  project_id = local.project_vars.locals.project_id
  prefix     = ""
  names = [
    "agent-${local.app_vars.locals.app_id}",
  ]
  project_roles = [
    "${local.project_vars.locals.project_id}=>roles/aiplatform.user",
    "${local.project_vars.locals.project_id}=>roles/logging.logWriter",
    "${local.project_vars.locals.project_id}=>roles/monitoring.metricWriter",
    "${local.project_vars.locals.project_id}=>roles/secretmanager.secretAccessor",
    "${local.project_vars.locals.project_id}=>roles/serviceusage.serviceUsageConsumer",
  ]
}
