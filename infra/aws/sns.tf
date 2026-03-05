# SNS for Alerting
# Note: Individual alert topics are created via API by users
# This file contains shared SNS resources and IAM policies

# IAM policy for Lambda to publish to SNS
data "aws_iam_policy_document" "sns_publish" {
  statement {
    effect = "Allow"
    actions = [
      "sns:Publish"
    ]
    resources = [
      "arn:aws:sns:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${var.project_name}-*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "sns:CreateTopic",
      "sns:DeleteTopic",
      "sns:GetTopicAttributes",
      "sns:SetTopicAttributes",
      "sns:ListSubscriptionsByTopic",
      "sns:Subscribe",
      "sns:Unsubscribe",
      "sns:ListTagsForResource"
    ]
    resources = [
      "arn:aws:sns:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${var.project_name}-*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "sns:ListTopics"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "sns_publish" {
  name        = "${var.project_name}-sns-publish-${var.environment}"
  description = "Allow Lambda to publish to SNS topics and manage alert topics"
  policy      = data.aws_iam_policy_document.sns_publish.json
}
