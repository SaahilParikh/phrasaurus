output "function_url" {
  description = "Public HTTPS endpoint for the Lambda — frontend POSTs here."
  value       = aws_lambda_function_url.phrasaurus.function_url
}

output "deploy_role_arn" {
  description = "IAM role ARN for the GitHub Actions deploy.yml workflow to assume via OIDC."
  value       = aws_iam_role.github_deploy.arn
}

output "terraform_ci_role_arn" {
  description = "IAM role ARN for the infra.yml workflow. Created out-of-band during bootstrap; surfaced here for convenience."
  value       = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/phrasaurus-terraform-ci"
}

output "lambda_function_name" {
  description = "Lambda function name — the deploy workflow targets this for update-function-code."
  value       = "phrasaurus-lambda"
}

output "frontend_bucket_name" {
  description = "S3 bucket hosting the static frontend."
  value       = "phrasaurus.com"
}
