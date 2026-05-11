# ---------------------------------------------------------------------------
# Data sources — pre-existing resources we reference but don't own.
# ---------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

# OIDC provider ARN is fully determined by the account ID, so we construct it
# rather than using a data source. Avoids needing iam:ListOpenIDConnectProviders
# on the terraform-ci role.
locals {
  github_oidc_provider_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/token.actions.githubusercontent.com"
}

# Bedrock model ARNs Terraform doesn't manage — referenced for the IAM policy.
locals {
  account_id  = data.aws_caller_identity.current.account_id
  region      = "us-east-1"
  github_repo = "SaahilParikh/phrasaurus"
  lambda_name = "phrasaurus-lambda"
  lambda_role = "phrasaurus-lambda-role-86yuzts9"
  bucket_name = "phrasaurus.com"

  bedrock_model_arn   = "arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0"
  bedrock_profile_arn = "arn:aws:bedrock:*:${local.account_id}:inference-profile/us.anthropic.claude-haiku-4-5-20251001-v1:0"

  lambda_arn = "arn:aws:lambda:${local.region}:${local.account_id}:function:${local.lambda_name}"
}

# ---------------------------------------------------------------------------
# Inline Bedrock-invoke policy on the existing Lambda runtime role.
# aws_iam_role_policy manages ONLY this inline policy — it does not
# own the role itself. No import needed.
# ---------------------------------------------------------------------------

resource "aws_iam_role_policy" "lambda_bedrock_invoke" {
  name = "phrasaurus-bedrock-invoke"
  role = local.lambda_role

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "bedrock:InvokeModel"
      Resource = [local.bedrock_model_arn, local.bedrock_profile_arn]
    }]
  })
}

# ---------------------------------------------------------------------------
# Lambda Function URL — public HTTPS entry point for the browser frontend.
# CORS is handled here; the handler also emits headers defensively.
# ---------------------------------------------------------------------------

resource "aws_lambda_function_url" "phrasaurus" {
  function_name      = local.lambda_name
  authorization_type = "NONE"

  cors {
    allow_origins = ["*"]
    allow_methods = ["POST"]
    allow_headers = ["content-type"]
    max_age       = 3600
  }
}

# Required with authorization_type=NONE: grant any principal permission
# to invoke the function URL (the URL itself is the access control).
resource "aws_lambda_permission" "public_invoke_url" {
  statement_id           = "AllowPublicFunctionUrlInvoke"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = local.lambda_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

# As of October 2025, Function URLs with auth NONE also require an
# lambda:InvokeFunction allow on the function itself — the auto-generated
# FunctionURLAllowPublicAccess statement only covers InvokeFunctionUrl, which
# would leave the URL returning 403 Forbidden.
resource "aws_lambda_permission" "public_invoke_function" {
  statement_id  = "AllowPublicInvokeFunction"
  action        = "lambda:InvokeFunction"
  function_name = local.lambda_name
  principal     = "*"
}

# ---------------------------------------------------------------------------
# S3 bucket policy — public read on ALL objects (needed for the split
# frontend: index.html + styles.css + app.js + …).
# ---------------------------------------------------------------------------

resource "aws_s3_bucket_policy" "phrasaurus_com" {
  bucket = local.bucket_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "PublicReadGetObject"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:GetObject"
      Resource  = "arn:aws:s3:::${local.bucket_name}/*"
    }]
  })
}

# ---------------------------------------------------------------------------
# GitHub Actions deploy role — assumed by the deploy workflow via OIDC.
# Scoped to this repo + main branch. Separate from the terraform-ci role
# so the hot-path deploy credentials cannot mutate infrastructure.
# ---------------------------------------------------------------------------

resource "aws_iam_role" "github_deploy" {
  name        = "phrasaurus-github-deploy"
  description = "GitHub Actions role used by deploy.yml for Lambda code + S3 sync"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = local.github_oidc_provider_arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:${local.github_repo}:ref:refs/heads/main"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_deploy_permissions" {
  name = "deploy-permissions"
  role = aws_iam_role.github_deploy.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LambdaCodeAndConfig"
        Effect = "Allow"
        Action = [
          "lambda:UpdateFunctionCode",
          "lambda:UpdateFunctionConfiguration",
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration",
          "lambda:PublishVersion",
          "lambda:GetFunctionUrlConfig",
        ]
        Resource = local.lambda_arn
      },
      {
        Sid    = "FrontendBucket"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:GetObject",
          "s3:ListBucket",
        ]
        Resource = [
          "arn:aws:s3:::${local.bucket_name}",
          "arn:aws:s3:::${local.bucket_name}/*",
        ]
      },
    ]
  })
}
