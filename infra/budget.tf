# Monthly spend guardrail for phrasaurus resources.
#
# Filter: user-defined cost-allocation tag Project=phrasaurus. This catches
# tagged resources (Lambda, S3, log group, guardrail). It may not capture
# all Bedrock invocation charges — Bedrock bills at the service level and
# may not attribute to the invoking Lambda's tags. For a personal account
# where phrasaurus is the only Bedrock consumer, the tag filter is usually
# sufficient; add a service-scoped budget if that changes.
#
# Alerts fire at 50/80/100% actual spend and 100% forecasted spend, all to
# the configured notification email.

variable "budget_notification_email" {
  description = "Email to notify when phrasaurus spend crosses budget thresholds."
  type        = string
  default     = "SaahilParikh2000@gmail.com"
}

variable "budget_monthly_limit_usd" {
  description = "Monthly spend ceiling for phrasaurus in USD."
  type        = number
  default     = 25
}

resource "aws_budgets_budget" "phrasaurus_monthly" {
  name         = "phrasaurus-monthly"
  budget_type  = "COST"
  time_unit    = "MONTHLY"
  limit_amount = tostring(var.budget_monthly_limit_usd)
  limit_unit   = "USD"

  cost_filter {
    name   = "TagKeyValue"
    values = ["user:Project$phrasaurus"]
  }

  # 50% actual spend
  notification {
    notification_type          = "ACTUAL"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.budget_notification_email]
  }

  # 80% actual spend
  notification {
    notification_type          = "ACTUAL"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.budget_notification_email]
  }

  # 100% actual spend
  notification {
    notification_type          = "ACTUAL"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.budget_notification_email]
  }

  # 100% forecasted spend (projected month-end)
  notification {
    notification_type          = "FORECASTED"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.budget_notification_email]
  }
}
