resource "aws_dynamodb_table" "ledger" {
  name         = "splitly"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

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
