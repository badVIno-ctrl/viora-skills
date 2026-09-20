"""Fixture f03 — negative samples. None of these may produce a finding.

Same variable names, values that only look like credentials to a careless
regex: documentation placeholders, env indirection and truncated shapes.
"""
import os

AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]          # SECRET-001 negative
client_secret = os.getenv("AZURE_CLIENT_SECRET", "")          # SECRET-016 negative
AZURE_STORAGE = "DefaultEndpointsProtocol=https;AccountName=<name>;AccountKey=<key>"  # SECRET-017 negative
GCP_KEY = {"type": "authorized_user", "client_email": "you@example.com"}  # SECRET-018 negative
VERCEL_TOKEN = "<your-vercel-token>"                          # SECRET-019 negative
SUPABASE_ANON = "set SUPABASE_ANON_KEY in the environment"    # SECRET-020 negative
CLOUDFLARE_API_TOKEN = "REPLACE_ME"                           # SECRET-021 negative
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")               # SECRET-022 negative
HF_TOKEN = "hf_short"                                         # SECRET-023 negative
DOCKER_PAT = "dckr_pat_"                                      # SECRET-024 negative
AGE_IDENTITY = "AGE-PUBLIC-KEY-1EXAMPLE"                      # SECRET-025 negative
FCM_SERVER_KEY = "see docs/firebase.md for how to provision"  # SECRET-026 negative
