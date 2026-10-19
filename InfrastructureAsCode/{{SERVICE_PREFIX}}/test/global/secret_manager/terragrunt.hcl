# The original template sourced these from a private internal Terraform module
# library. Point this at your own module (or a public registry equivalent) - the
# inputs below describe exactly what the module has to accept.
terraform {
  source = "<your-module-registry>/gcp_secret_manager"
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

  gcp_secret_items = ({

    "gateway-vk" = {
      secret_id = "gateway-vk-${local.app_vars.locals.app_id}"
      labels = {
        terraform = "true"
      }
      secret_iam = ({
        secretAccessor = {
          role = "roles/secretmanager.secretAccessor"
          members = [
            "serviceAccount:agent-${local.app_vars.locals.app_id}@${local.project_vars.locals.project_id}.iam.gserviceaccount.com",
          ]
        }
      })
    }

  })
}
