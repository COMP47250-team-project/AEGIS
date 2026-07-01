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

@description('AEGIS-77: object ID of the deploying user — granted Key Vault secret management. Get it with: az ad signed-in-user show --query id -o tsv')
param deployerObjectId string = ''

@description('AEGIS-77: wire the backend Container App to read secrets from Key Vault. Deploy once with this false to create the vault, set the secrets (see README), then redeploy with true.')
param wireKeyVaultSecrets bool = false

// Short, stable suffix for globally-unique names (ACR, Postgres, Storage, SB).
var suffix = uniqueString(resourceGroup().id)
var prefix = 'aegis${environmentName}'

// Key Vault name must be <= 24 chars; build it from the name var so the backend
// app can reference its secrets without depending on the keyVault module
// (avoids a dependency cycle: keyVault needs the app's identity principalId).
var keyVaultName = take('${prefix}kv${suffix}', 24)
var keyVaultSecretBase = 'https://${keyVaultName}${environment().suffixes.keyvaultDns}/secrets/'
var backendKeyVaultSecrets = wireKeyVaultSecrets
  ? [
      {
        envVarName: 'DATABASE_URL'
        secretName: 'database-url'
        keyVaultUrl: '${keyVaultSecretBase}database-url'
      }
      {
        envVarName: 'JWT_SECRET'
        secretName: 'jwt-secret'
        keyVaultUrl: '${keyVaultSecretBase}jwt-secret'
      }
      {
        envVarName: 'AZURE_SERVICE_BUS_CONNECTION_STRING'
        secretName: 'service-bus-connection-string'
        keyVaultUrl: '${keyVaultSecretBase}service-bus-connection-string'
      }
      {
        envVarName: 'AZURE_STORAGE_CONNECTION_STRING'
        secretName: 'storage-connection-string'
        keyVaultUrl: '${keyVaultSecretBase}storage-connection-string'
      }
    ]
  : []

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
    // 'psql' (not 'pg'): a failed westeurope attempt left an orphaned
    // 'aegisdev-pg-<suffix>' record that blocks recreating the same name in a
    // new region, so use a fresh name.
    name: '${prefix}-psql-${suffix}'
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
    keyVaultSecrets: backendKeyVaultSecrets
  }
}

// AEGIS-77: Key Vault holding the production secrets. Access-policy model
// grants the deploying user secret management and the backend app's managed
// identity secret read. Built after backendApp so its identity exists.
module keyVault 'modules/keyVault.bicep' = {
  name: 'keyVault'
  params: {
    name: keyVaultName
    location: location
    tenantId: subscription().tenantId
    deployerObjectId: deployerObjectId
    readerPrincipalIds: [
      backendApp.outputs.principalId
    ]
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
output keyVaultUri string = keyVault.outputs.vaultUri
output keyVaultName string = keyVault.outputs.vaultName

// Ticket requires connection strings as outputs; move to Key Vault in AEGIS-25.
#disable-next-line outputs-should-not-contain-secrets
output databaseUrl string = 'postgresql://${postgresAdminLogin}:${postgresAdminPassword}@${postgres.outputs.fqdn}:5432/${postgres.outputs.databaseName}'

// Ticket requires connection strings as outputs; move to Key Vault in AEGIS-25.
#disable-next-line outputs-should-not-contain-secrets
output serviceBusConnectionString string = serviceBus.outputs.connectionString

// Ticket requires connection strings as outputs; move to Key Vault in AEGIS-25.
#disable-next-line outputs-should-not-contain-secrets
output storageConnectionString string = storage.outputs.connectionString
