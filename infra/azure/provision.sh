#!/usr/bin/env bash
# AEGIS-21 — Provision the Azure environment (bash).
#
# Prerequisites:
#   1. Azure CLI installed (https://aka.ms/installazurecli) + Bicep: az bicep install
#   2. Logged in:  az login
#   3. Edit main.bicepparam with the M1 + M5 alert emails.
#   4. Fill in the variables below.
#
# Run from this folder:  ./provision.sh
set -euo pipefail

# ── Fill these in ────────────────────────────────────────────────────────────
SUBSCRIPTION_ID="<your-subscription-id>"
LOCATION="westeurope"
# M1 (Vijeth) and M5 (DevOps lead) — UPN/email of each Azure AD user.
CONTRIBUTORS=("REPLACE_WITH_M1_EMAIL" "REPLACE_WITH_M5_EMAIL")

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

az account set --subscription "$SUBSCRIPTION_ID"

echo "==> Deploying resource group + budget (Bicep)..."
az deployment sub create \
  --name aegis-bootstrap \
  --location "$LOCATION" \
  --template-file "$here/main.bicep" \
  --parameters "$here/main.bicepparam"

echo "==> Assigning Contributor role to M1 + M5..."
scope="/subscriptions/$SUBSCRIPTION_ID"
for principal in "${CONTRIBUTORS[@]}"; do
  az role assignment create --assignee "$principal" --role "Contributor" --scope "$scope"
done

echo ""
echo "==> Done. Verify in the portal, then document the Subscription ID in the team Google Doc:"
echo "    $SUBSCRIPTION_ID"
