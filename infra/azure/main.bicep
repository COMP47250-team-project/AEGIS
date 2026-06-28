// AEGIS-21 — Azure environment bootstrap (subscription scope).
//
// Creates the project resource group and a monthly cost budget with email
// alerts. Role assignments are handled by provision.ps1 / provision.sh, since
// the Azure CLI can resolve users by email (Bicep needs raw object IDs).
//
// Deploy:
//   az deployment sub create --location <region> \
//     --template-file main.bicep --parameters main.bicepparam

targetScope = 'subscription'

@description('Resource group name.')
param resourceGroupName string = 'aegis-prod-rg'

@description('Azure region for the resource group.')
param location string = 'westeurope'

@description('Monthly budget amount, in the subscription billing currency (assumed EUR).')
param budgetAmount int = 30

@description('Budget resource name.')
param budgetName string = 'aegis-monthly-budget'

@description('First day of the budget period (yyyy-MM-01). Defaults to the current month.')
param budgetStartDate string = utcNow('yyyy-MM-01')

@description('Email addresses notified when budget thresholds are crossed (M1 + M5).')
param alertEmails array

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
}

// Subscription-wide monthly cost budget. Alerts at 80% and 100% of actual
// spend, plus a forecast alert at 100% so we hear about it before we hit it.
resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: budgetName
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
    }
    notifications: {
      actual_80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: alertEmails
      }
      actual_100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Actual'
        contactEmails: alertEmails
      }
      forecast_100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: alertEmails
      }
    }
  }
}

output resourceGroupId string = resourceGroup.id
