# §C31 — VAPID keys live in Parameter Store.
#
# §C47 forbids credentials in .tf, so these are created with placeholders and
# the real values are put out of band by CLI. The resources are still born in
# Terraform (§C42); only the values are not.
#
# Caveat worth knowing: `ignore_changes` stops Terraform *writing* the value,
# but a refresh still reads it into state. The state bucket is private,
# versioned and encrypted, and reachable only by an MFA-gated role or CI —
# that is the mitigation, not an argument that the exposure is absent.

resource "aws_ssm_parameter" "vapid_private_key" {
  name  = "/splitly/vapid/private_key"
  type  = "SecureString"
  value = "placeholder-set-out-of-band"

  lifecycle {
    ignore_changes = [value]
  }
}

# Not a secret — the browser needs it to subscribe (T10). Kept here so the
# pair lives in one place.
resource "aws_ssm_parameter" "vapid_public_key" {
  name  = "/splitly/vapid/public_key"
  type  = "String"
  value = "placeholder-set-out-of-band"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "vapid_subject" {
  name  = "/splitly/vapid/subject"
  type  = "String"
  value = "placeholder-set-out-of-band"

  lifecycle {
    ignore_changes = [value]
  }
}

data "aws_caller_identity" "current" {}

resource "aws_iam_role_policy" "api_vapid" {
  name = "vapid-read"
  role = aws_iam_role.api.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter", "ssm:GetParameters"]
        Resource = "arn:aws:ssm:us-east-1:${data.aws_caller_identity.current.account_id}:parameter/splitly/vapid/*"
      },
      {
        # SecureString is decrypted with the AWS-managed SSM key. Scoped so
        # the role cannot decrypt anything except through SSM.
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = "*"
        Condition = {
          StringEquals = { "kms:ViaService" = "ssm.us-east-1.amazonaws.com" }
        }
      },
    ]
  })
}
