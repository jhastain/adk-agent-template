locals {
  env_var        = read_terragrunt_config("env.hcl")
  app_var        = read_terragrunt_config(find_in_parent_folders("app.hcl"))
  project_id     = "${local.app_var.locals.app_id}-${local.env_var.locals.environment}-project"
  project_number = run_cmd("--terragrunt-quiet", "gcloud", "projects", "describe", local.project_id, "--format=value(projectNumber)")
}
