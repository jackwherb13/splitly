locals {
  api_function_name = "splitly-api"
}

# Build artifacts live in one gitignored place (§C37). CI takes this over
# at T20 so code deploys stop needing an MFA-gated apply (§C34).
data "archive_file" "api" {
  type        = "zip"
  source_dir  = "${path.module}/../api/src"
  output_path = "${path.module}/../dist/lambda/api.zip"
  excludes    = ["**/__pycache__/**"]
}

resource "aws_iam_role" "api" {
  name = "splitly-api-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Logs only. DynamoDB access arrives with T7, when a handler first needs it.
resource "aws_iam_role_policy_attachment" "api_logs" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# No UpdateItem, no DeleteItem. §V8 is enforced at the IAM layer as well as
# by the absence of store methods — a bug cannot mutate what the role
# has no permission to touch.
resource "aws_iam_role_policy" "api_ledger" {
  name = "ledger-access"
  role = aws_iam_role.api.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"]
      Resource = aws_dynamodb_table.ledger.arn
    }]
  })
}

# §T11.5 — adding a member creates their login. This pool only, and no
# update, delete or password action.
resource "aws_iam_role_policy" "api_cognito" {
  name = "member-create"
  role = aws_iam_role.api.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["cognito-idp:AdminCreateUser", "cognito-idp:AdminGetUser"]
      Resource = aws_cognito_user_pool.main.arn
    }]
  })
}

# Born here rather than auto-created by Lambda, which would never expire (§C42).
resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.api_function_name}"
  retention_in_days = 14
}

resource "aws_lambda_function" "api" {
  function_name    = local.api_function_name
  role             = aws_iam_role.api.arn
  runtime          = "python3.11"
  handler          = "splitly.handler.handle"
  filename         = data.archive_file.api.output_path
  source_code_hash = data.archive_file.api.output_base64sha256
  layers           = [aws_lambda_layer_version.deps.arn] # pywebpush, for the nudge route (T12)
  timeout          = 10
  memory_size      = 256

  environment {
    variables = {
      SPLITLY_TABLE        = aws_dynamodb_table.ledger.name
      SPLITLY_USER_POOL_ID = aws_cognito_user_pool.main.id
    }
  }

  depends_on = [aws_cloudwatch_log_group.api]
}

resource "aws_apigatewayv2_api" "main" {
  name          = "splitly"
  protocol_type = "HTTP"

  # The real origin, not "*". No credentials: the token rides in the
  # Authorization header, so cookies are never in play.
  cors_configuration {
    allow_origins = ["https://${aws_cloudfront_distribution.web.domain_name}"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["authorization", "content-type"]
    max_age       = 300
  }
}

# §V10's first half is infrastructure, not code: API Gateway verifies the
# Cognito token before Lambda is invoked at all.
resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.main.id
  name             = "cognito"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.web.id]
    # Region is pinned single by §C46.
    issuer = "https://cognito-idp.us-east-1.amazonaws.com/${aws_cognito_user_pool.main.id}"
  }
}

resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "me" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /me"
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "entries_create" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /entries"
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "entries_list" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /entries"
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "members_list" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /members"
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "balances_list" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /balances"
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "member_set_active" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "PUT /members/{member_id}"
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "member_create" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /members"
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "nudge_create" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /nudges"
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "write_off_create" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /write-offs"
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "subscription_create" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /subscriptions"
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

output "api_endpoint" {
  value = aws_apigatewayv2_stage.default.invoke_url
}
