# §C26 — the PWA is served over https because a service worker requires it.
# The default *.cloudfront.net certificate covers that, so no ACM cert and no
# domain are needed yet. A custom domain is a later, additive change.

resource "aws_s3_bucket" "web" {
  bucket = "splitly-web-725423737107"
}

# The bucket is private. CloudFront reaches it through OAC, nothing else does.
resource "aws_s3_bucket_public_access_block" "web" {
  bucket                  = aws_s3_bucket.web.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "web" {
  name                              = "splitly-web"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

data "aws_iam_policy_document" "web" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.web.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.web.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "web" {
  bucket = aws_s3_bucket.web.id
  policy = data.aws_iam_policy_document.web.json
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

# A cache policy stops CloudFront caching. It does not tell the browser
# anything — that needs a response headers policy, or S3 sends no
# Cache-Control at all and the browser caches heuristically (§R13).
resource "aws_cloudfront_response_headers_policy" "no_cache" {
  name = "splitly-no-cache"

  custom_headers_config {
    items {
      header   = "Cache-Control"
      value    = "no-cache"
      override = true
    }
  }
}

resource "aws_cloudfront_distribution" "web" {
  enabled             = true
  default_root_object = "index.html"
  # US + Europe only. Four people (§C20).
  price_class = "PriceClass_100"

  origin {
    origin_id                = "s3"
    domain_name              = aws_s3_bucket.web.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.web.id
  }

  default_cache_behavior {
    target_origin_id       = "s3"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.optimized.id
  }

  # A cached service worker never updates, and the failure is silent: installed
  # apps keep running old code forever. Same for the HTML that names the hashed
  # bundles. Everything else is content-hashed and safe to cache hard.
  ordered_cache_behavior {
    path_pattern               = "/sw.js"
    target_origin_id           = "s3"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.no_cache.id
  }

  ordered_cache_behavior {
    path_pattern               = "/index.html"
    target_origin_id           = "s3"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.no_cache.id
  }

  # Client-side routing: unknown paths are React's to resolve, not S3's.
  # A private bucket answers a missing key with 403, so both are mapped.
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
}

output "web_url" {
  value = "https://${aws_cloudfront_distribution.web.domain_name}"
}

output "web_bucket" {
  value = aws_s3_bucket.web.id
}

output "web_distribution_id" {
  value = aws_cloudfront_distribution.web.id
}
