resource "aws_cognito_user_pool" "main" {
  name = "splitly"

  # §C4 — nobody signs themselves up.
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # Email OTP is an Essentials feature. Lite does not have it.
  user_pool_tier = "ESSENTIALS"

  sign_in_policy {
    allowed_first_auth_factors = ["EMAIL_OTP"]
  }

  # Required by the API even though nobody will ever type one.
  password_policy {
    minimum_length = 8
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
}

resource "aws_cognito_user_pool_client" "web" {
  name         = "splitly-web"
  user_pool_id = aws_cognito_user_pool.main.id

  # A browser app cannot keep a secret.
  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.web.id
}
