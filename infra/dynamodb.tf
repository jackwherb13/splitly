resource "aws_dynamodb_table" "ledger" {
  name         = "splitly"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  # §C29 — entry writes drive notifications (stream.tf).
  stream_enabled   = true
  stream_view_type = "NEW_IMAGE"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  # This table is the ledger. Losing it is unrecoverable.
  lifecycle {
    prevent_destroy = true
  }
}
