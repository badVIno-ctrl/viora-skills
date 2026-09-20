"""Fixture f03 — positive samples. Every value here is invented and inert.

One line per rule the scanner must catch. Nothing in this file is a live
credential; the point is the shape, not the value.
"""

# SECRET-001 AWS access key ID
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"

# SECRET-016 Azure AD client secret
client_secret = "abc8Q~kQv2Lm9Xy4Tz7Rd1Nf6Pw3Hs0Bg5Jc8"

# SECRET-017 Azure Storage connection string
AZURE_STORAGE = "DefaultEndpointsProtocol=https;AccountName=fixturestore;AccountKey=Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5MGFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6QUJDRA=="

# SECRET-018 GCP service account
GCP_KEY = {"type": "service_account", "client_email": "fixture@demo-project.iam.gserviceaccount.com"}

# SECRET-019 Vercel token
VERCEL_TOKEN = "ab12Cd34Ef56Gh78Ij90Kl12"

# SECRET-020 Supabase service_role JWT
SUPABASE_SERVICE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoic3VwYWJhc2UifQ.c2lnbmF0dXJlLWZpeHR1cmUtdmFsdWU"

# SECRET-021 Cloudflare API token
CLOUDFLARE_API_TOKEN = "v1abcdefghijklmnopqrstuvwxyz0123456789AB"

# SECRET-022 Discord bot token (first segment decodes to text, not a snowflake,
#             so upstream push-protection scanners treat it as the fake it is)
DISCORD_TOKEN = "Mm9ub3Rhc25vd2ZsYWtlXzk5.Gh1Jk2.L3m4N5o6P7q8R9s0T1u2V3w4X5y6Z7a8B9c"

# SECRET-023 HuggingFace token
HF_TOKEN = "hf_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"

# SECRET-024 Docker Hub PAT
DOCKER_PAT = "dckr_pat_AbCdEfGhIjKlMnOpQrStUvWx12"

# SECRET-025 age identity
AGE_IDENTITY = "AGE-SECRET-KEY-1QQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQ"

# SECRET-026 Firebase server key
FCM_SERVER_KEY = "AAAAbCdEfGh:APA91bZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"
