# Azure environment provisioning (AEGIS-21)

Infrastructure-as-Code to bootstrap the AEGIS Azure environment:

- Resource group **`aegis-prod-rg`** in **West Europe**
- A **subscription-wide monthly budget of €30** with email alerts (80% / 100% actual, 100% forecast)
- **Contributor** role for M1 (Vijeth) and M5 (DevOps lead)

## Files

| File | Purpose |
|------|---------|
| `main.bicep` | Declares the resource group + cost budget (subscription scope) |
| `main.bicepparam` | Parameter values — **edit the alert emails here** |
| `provision.ps1` | Windows runner: deploys Bicep + assigns roles |
| `provision.sh` | macOS/Linux runner (same steps) |

## Prerequisites

1. **Azure CLI** — https://aka.ms/installazurecli
2. **Bicep**: `az bicep install`
3. **Sign in**: `az login` (and confirm the right subscription: `az account show`)
4. You must have **Owner** or **User Access Administrator** on the subscription to assign roles (a student subscription normally makes you Owner).

## Steps

1. **Edit `main.bicepparam`** — replace the two `REPLACE_WITH_*_EMAIL` placeholders with the Azure AD emails of M1 and M5.
2. **Edit the runner** (`provision.ps1` or `provision.sh`) — set `SubscriptionId`/`SUBSCRIPTION_ID` and the two `Contributors`/`CONTRIBUTORS` emails.
3. **Dry-run first** (recommended) to preview changes:
   ```bash
   az deployment sub what-if --location westeurope \
     --template-file main.bicep --parameters main.bicepparam
   ```
4. **Run it:**
   - Windows: `./provision.ps1`
   - macOS/Linux: `./provision.sh`

## Verify (acceptance criteria)

- **Resource group**: `az group show -n aegis-prod-rg` → exists in West Europe.
- **Budget**: Azure Portal → *Cost Management → Budgets* → `aegis-monthly-budget` shows €30 / Monthly.
- **Roles**: `az role assignment list --scope /subscriptions/<id> --query "[?roleDefinitionName=='Contributor'].principalName"` → lists M1 + M5.
- **Subscription ID** → paste into the team **Google Doc** (do **not** commit it to git — it's account metadata, kept in Drive like our other docs).

## Notes

- **Currency**: Azure budgets use the subscription's billing currency. If yours bills in USD, the `€30` figure maps to a USD amount — adjust `budgetAmount` in `main.bicepparam` accordingly.
- **Idempotent**: re-running is safe — the resource group and budget are upserted by name.
- **Re-run after changes**: editing `main.bicepparam` and re-deploying updates the budget in place.
