# AEGIS-21 — Provision the Azure environment (PowerShell).
#
# Prerequisites:
#   1. Azure CLI installed (https://aka.ms/installazurecli) + Bicep:  az bicep install
#   2. Logged in:  az login
#   3. Edit main.bicepparam with the M1 + M5 alert emails.
#   4. Fill in the variables below.
#
# Run from this folder:  ./provision.ps1

$ErrorActionPreference = 'Stop'

# ── Fill these in ────────────────────────────────────────────────────────────
$SubscriptionId = '<your-subscription-id>'
$Location       = 'westeurope'
# M1 (Vijeth) and M5 (DevOps lead) — UPN/email of each Azure AD user.
$Contributors   = @('REPLACE_WITH_M1_EMAIL', 'REPLACE_WITH_M5_EMAIL')

$here = $PSScriptRoot

az account set --subscription $SubscriptionId

Write-Host '==> Deploying resource group + budget (Bicep)...'
az deployment sub create `
  --name aegis-bootstrap `
  --location $Location `
  --template-file "$here/main.bicep" `
  --parameters "$here/main.bicepparam"

Write-Host '==> Assigning Contributor role to M1 + M5...'
$scope = "/subscriptions/$SubscriptionId"
foreach ($principal in $Contributors) {
  az role assignment create --assignee $principal --role 'Contributor' --scope $scope
}

Write-Host ''
Write-Host '==> Done. Verify in the portal, then document the Subscription ID in the team Google Doc:'
Write-Host "    $SubscriptionId"
