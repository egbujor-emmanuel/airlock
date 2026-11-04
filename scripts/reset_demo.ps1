# Put both demo repos back to their broken starting state (the bug reproduces again)
# and regenerate each org's private data and canaries. Run before every demo.
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
git checkout -- demo/acme-app demo/payco-sdk
git clean -fdq -- demo/acme-app demo/payco-sdk -e node_modules -e .env -e logs -e INTERNAL_NOTES.md
uv run python scripts/make_fixtures.py
Pop-Location
