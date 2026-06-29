using './main.bicep'

// dev | prod — drives the resource name prefix.
param environmentName = 'dev'

// PostgreSQL admin password — DO NOT hard-code a real value here.
// Pass it at deploy time instead, e.g.:
//   az deployment group create -g aegis-prod-rg --template-file infra/main.bicep \
//     --parameters infra/main.bicepparam postgresAdminPassword='<strong-secret>'
param postgresAdminPassword = ''

// Container images default to public placeholders in main.bicep; override once
// CI has pushed real images to ACR:
// param backendImage = '<acr>.azurecr.io/backend:latest'
// param frontendImage = '<acr>.azurecr.io/frontend:latest'
