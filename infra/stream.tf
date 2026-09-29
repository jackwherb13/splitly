# §C29, §I `strm` — an entry written → DynamoDB Streams → Lambda → push (§T11).
#
# Its own role: it reads the stream and queries the table. Its one write is
# retiring a dead push subscription (§V7); §V27 keeps that write to existing
# PUSHSUB# items, so §V8 is held by the code, as it is for the API role.

locals {
  stream_function_name = "splitly-stream"
}

# `pywebpush` is not in the runtime. Built by `npm run build` into dist/
# (§C37) — see api/scripts/build_layer.py for why the platform is pinned.
data "archive_file" "deps_layer" {
  type        = "zip"
  source_dir  = "${path.module}/../dist/lambda/layer"
  output_path = "${path.module}/../dist/lambda/layer.zip"
}

resource "aws_lambda_layer_version" "deps" {
  layer_name          = "splitly-deps"
  filename            = data.archive_file.deps_layer.output_path
  source_code_hash    = data.archive_file.deps_layer.output_base64sha256
  compatible_runtimes = ["python3.11"]
}

resource "aws_iam_role" "stream" {
  name = "splitly-stream-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Logs, plus reading any DynamoDB stream.
resource "aws_iam_role_policy_attachment" "stream_exec" {
  role       = aws_iam_role.stream.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaDynamoDBExecutionRole"
}

resource "aws_iam_role_policy" "stream_ledger" {
  name = "ledger-read-retire-subs"
  role = aws_iam_role.stream.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:Query", "dynamodb:PutItem"]
      Resource = aws_dynamodb_table.ledger.arn
    }]
  })
}

resource "aws_iam_role_policy" "stream_vapid" {
  name   = "vapid-read"
  role   = aws_iam_role.stream.id
  policy = local.vapid_read_policy
}

resource "aws_cloudwatch_log_group" "stream" {
  name              = "/aws/lambda/${local.stream_function_name}"
  retention_in_days = 14
}

resource "aws_lambda_function" "stream" {
  function_name    = local.stream_function_name
  role             = aws_iam_role.stream.arn
  runtime          = "python3.11"
  handler          = "splitly.stream.handle"
  filename         = data.archive_file.api.output_path
  source_code_hash = data.archive_file.api.output_base64sha256
  layers           = [aws_lambda_layer_version.deps.arn]
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      SPLITLY_TABLE = aws_dynamodb_table.ledger.name
    }
  }

  depends_on = [aws_cloudwatch_log_group.stream]
}

# Send failures are swallowed in code, so a retry here only follows a crash
# before any send — bounded anyway, so a poison record cannot loop for a day.
resource "aws_lambda_event_source_mapping" "ledger_stream" {
  event_source_arn       = aws_dynamodb_table.ledger.stream_arn
  function_name          = aws_lambda_function.stream.arn
  starting_position      = "LATEST"
  batch_size             = 10
  maximum_retry_attempts = 2
}
