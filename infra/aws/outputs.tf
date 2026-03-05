output "project_name" {
  description = "Project name"
  value       = var.project_name
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

output "api_url" {
  description = "API Gateway URL"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "cloudfront_url" {
  description = "CloudFront distribution URL"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.frontend.id
}

output "s3_bucket_name" {
  description = "S3 bucket name for frontend"
  value       = aws_s3_bucket.frontend.id
}

output "cognito_domain" {
  description = "Cognito hosted UI domain"
  value       = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.aws_region}.amazoncognito.com"
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  description = "Cognito User Pool Client ID"
  value       = aws_cognito_user_pool_client.main.id
}

output "dynamodb_table_name" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.pulsechecks.name
}

output "dynamodb_table_arn" {
  description = "DynamoDB table ARN"
  value       = aws_dynamodb_table.pulsechecks.arn
}

output "lambda_role_arn" {
  description = "Lambda execution role ARN"
  value       = aws_iam_role.lambda_exec.arn
}

output "sns_publish_policy_arn" {
  description = "IAM policy ARN for SNS publish permissions"
  value       = aws_iam_policy.sns_publish.arn
}

output "allowed_email_domains" {
  description = "Allowed email domains for authentication"
  value       = var.allowed_email_domains
}

output "api_function_name" {
  description = "API Lambda function name"
  value       = aws_lambda_function.api.function_name
}

output "ping_function_name" {
  description = "Ping Lambda function name"
  value       = aws_lambda_function.ping.function_name
}

output "late_detector_function_name" {
  description = "Late detector Lambda function name"
  value       = aws_lambda_function.late_detector.function_name
}

output "deployment_instructions" {
  description = "Next steps for deployment"
  value       = <<-EOT

    ✅ Infrastructure deployed successfully!

    Next steps:

    1. Update Google OAuth callback URL:
       ${aws_cognito_user_pool_domain.main.domain}.auth.${var.aws_region}.amazoncognito.com/oauth2/idpresponse

    2. Deploy via GitLab CI or manually:
       git push origin main

    3. Access your application:
       Frontend: https://${aws_cloudfront_distribution.frontend.domain_name}
       API: ${aws_apigatewayv2_api.main.api_endpoint}

  EOT
}
