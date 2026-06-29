// AEGIS-63 — full Azure environment for AEGIS.
//
// Deploy into the existing resource group (aegis-prod-rg from AEGIS-21):
//   az deployment group create -g aegis-prod-rg \
//     --template-file infra/main.bicep --parameters infra/main.bicepparam
//
// First run uses public placeholder container images so the deploy succeeds
// before CI has pushed real images to ACR; AEGIS-66 swaps in the real images
// and wires the connection strings into the Container App secrets.

targetScope = 'resourceGroup'

@description('Azure region (defaults to the resource group location).')
param location string = resourceGroup().location

@description('Region for PostgreSQL. Defaults to `location`, but some sponsored/student subscriptions restrict Flexible Server in certain regions (e.g. westeurope → LocationIsOfferRestricted); override this to an allowed region such as northeurope.')
param postgresLocation string = location

@description('Deployment environment.')
@allowed([
  'dev'
  'prod'
])
param environmentName string = 'dev'

@description('Backend container image (public placeholder until CI pushes the real one).')
param backendImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Frontend container image (public placeholder until CI pushes the real one).')
param frontendImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('PostgreSQL administrator login.')
param postgresAdminLogin string = 'aegisadmin'

@secure()
@description('PostgreSQL administrator password.')
param postgresAdminPassword string

// Short, stable suffix for globally-unique names (ACR, Postgres, Storage, SB).
var suffix = uniqueString(resourceGroup().id)
var prefix = 'aegis${environmentName}'

module acr 'modules/acr.bicep' = {
  name: 'acr'
  params: {
    name: '${prefix}acr${suffix}'
    location: location
  }
}

module containerEnv 'modules/containerAppEnv.bicep' = {
  name: 'containerAppEnv'
  params: {
    name: '${prefix}-cae'
    location: location
  }
}

module postgres 'modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    name: '${prefix}-pg-${suffix}'
    location: postgresLocation
    administratorLogin: postgresAdminLogin
    administratorPassword: postgresAdminPassword
  }
}

module serviceBus 'modules/serviceBus.bicep' = {
  name: 'serviceBus'
  params: {
    name: '${prefix}-sb-${suffix}'
    location: location
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    name: '${prefix}st${suffix}'
    location: location
  }
}

module backendApp 'modules/containerApp.bicep' = {
  name: 'backendApp'
  params: {
    name: 'backend-app'
    location: location
    environmentId: containerEnv.outputs.id
    image: backendImage
    cpu: '0.5'
    memory: '1Gi'
    minReplicas: 1
    targetPort: 8000
  }
}

module frontendApp 'modules/containerApp.bicep' = {
  name: 'frontendApp'
  params: {
    name: 'frontend-app'
    location: location
    environmentId: containerEnv.outputs.id
    image: frontendImage
    cpu: '0.25'
    memory: '0.5Gi'
    minReplicas: 1
    targetPort: 80
  }
}

// --- Outputs: connection strings + endpoints for AEGIS-66 / Key Vault (AEGIS-25) ---
output acrLoginServer string = acr.outputs.loginServer
output postgresFqdn string = postgres.outputs.fqdn
output serviceBusNamespace string = serviceBus.outputs.namespaceName
output storageAccountName string = storage.outputs.accountName
output backendFqdn string = backendApp.outputs.fqdn
output frontendFqdn string = frontendApp.outputs.fqdn

// Ticket requires connection strings as outputs; move to Key Vault in AEGIS-25.
#disable-next-line outputs-should-not-contain-secrets
output databaseUrl string = 'postgresql://${postgresAdminLogin}:${postgresAdminPassword}@${postgres.outputs.fqdn}:5432/${postgres.outputs.databaseName}'

// Ticket requires connection strings as outputs; move to Key Vault in AEGIS-25.
#disable-next-line outputs-should-not-contain-secrets
output serviceBusConnectionString string = serviceBus.outputs.connectionString

// Ticket requires connection strings as outputs; move to Key Vault in AEGIS-25.
#disable-next-line outputs-should-not-contain-secrets
output storageConnectionString string = storage.outputs.connectionString
