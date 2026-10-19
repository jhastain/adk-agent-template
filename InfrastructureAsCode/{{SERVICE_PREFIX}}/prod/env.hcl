locals {
  environment = basename(get_parent_terragrunt_dir("env.hcl"))
}
