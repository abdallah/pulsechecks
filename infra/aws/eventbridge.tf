# EventBridge rule for late detection (every 2 minutes)
resource "aws_cloudwatch_event_rule" "late_detector" {
  name                = "${var.project_name}-late-detector-${var.environment}"
  description         = "Trigger late detector every 2 minutes"
  schedule_expression = "rate(2 minutes)"

  tags = {
    Name = "${var.project_name}-late-detector-rule"
  }
}

# EventBridge target
resource "aws_cloudwatch_event_target" "late_detector" {
  rule      = aws_cloudwatch_event_rule.late_detector.name
  target_id = "LateDectorLambda"
  arn       = aws_lambda_function.late_detector.arn
}

# Lambda permission for EventBridge
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.late_detector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.late_detector.arn
}
