using './main.bicep'

// ── Fill these in before deploying ───────────────────────────────────────────
// Emails that receive the budget alerts — M1 (Vijeth) and M5 (DevOps lead).
param alertEmails = [
  'REPLACE_WITH_M1_EMAIL'
  'REPLACE_WITH_M5_EMAIL'
]

// Defaults below match the ticket; override only if needed.
// param resourceGroupName = 'aegis-prod-rg'
// param location = 'westeurope'
// param budgetAmount = 30
