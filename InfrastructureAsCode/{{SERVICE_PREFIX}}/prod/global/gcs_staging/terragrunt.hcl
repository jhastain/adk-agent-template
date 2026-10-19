# The original template sourced these from a private internal Terraform module
# library. Point this at your own module (or a public registry equivalent) - the
# inputs below describe exactly what the module has to accept.
terraform {
  source = "<your-module-registry>/gcp_bucket"
}

include "root" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  project_vars = read_terragrunt_config(find_in_parent_folders("project.hcl"))
  env_vars     = read_terragrunt_config(find_in_parent_folders("env.hcl"))
  app_vars     = read_terragrunt_config(find_in_parent_folders("app.hcl"))
}

inputs = {
  project_id = local.project_vars.locals.project_id
  prefix     = "${local.app_vars.locals.app_id}-${local.env_vars.locals.environment}"
  names      = ["agent-staging"]
  location   = "US"

  lifecycle_rules = [
    {
      action    = { type = "Delete" }
      condition = { age = "30" }
    }
  ]

  labels = {
    terraform   = "true"
    environment = local.env_vars.locals.environment
    purpose     = "agent-engine-staging"
  }
}
