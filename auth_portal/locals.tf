locals {
  function_name = "${var.naming_prefix}AuthPortal"

  # Hash of all Python source files for Lambda deployment
  source_hash = sha256(join("", [
    for f in fileset("${path.module}/src", "*.py") :
    filesha256("${path.module}/src/${f}")
  ]))
}
