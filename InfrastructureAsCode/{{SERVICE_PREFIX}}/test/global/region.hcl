locals {
  gcp_region              = basename("${get_parent_terragrunt_dir("region.hcl")}")
  gcp_region_split        = split("-", basename("${get_parent_terragrunt_dir("region.hcl")}"))
  gcp_region_short        = strcontains(local.gcp_region, "-") ? join("", [substr(local.gcp_region_split[1], 0, 1), substr(local.gcp_region_split[1], -1, 1)]) : local.gcp_region
  gcp_continent           = strcontains(local.gcp_region, "-") ? local.gcp_region_split[0] : local.gcp_region
  gcp_region_abbreviation = strcontains(local.gcp_region, "-") ? join("-", [local.gcp_continent, local.gcp_region_short]) : local.gcp_region
}
