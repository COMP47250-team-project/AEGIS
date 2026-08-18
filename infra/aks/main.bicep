// AEGIS — AKS provisioning (Kubernetes/Helm deployment track).
//
// Deploy into the existing resource group (aegis-prod-rg), ALONGSIDE the
// Container Apps stack from main.bicep — this does not touch or replace it:
//   az deployment group create -g aegis-prod-rg \
//     --template-file infra/aks/main.bicep --parameters infra/aks/main.bicepparam
//
// Validate without deploying:
//   az bicep build -f infra/aks/main.bicep
//   az deployment group what-if -g aegis-prod-rg -f infra/aks/main.bicep --parameters infra/aks/main.bicepparam
//
// The cluster pulls private images from the SAME ACR that main.bicep creates
// (aegis${env}acr${suffix}); this template references it as an existing
// resource and surfaces its login server as an output for the deploy workflow.

targetScope = 'resourceGroup'

@description('Azure region (defaults to the resource group location).')
param location string = resourceGroup().location

@description('Deployment environment.')
@allowed([
  'dev'
  'prod'
])
param environmentName string = 'dev'

@description('Node count for the AKS system node pool.')
param nodeCount int = 2

@description('Node VM size for the AKS system node pool.')
param nodeVmSize string = 'Standard_B2s_v2'

// Same naming scheme as main.bicep: stable suffix + env-prefixed names.
var suffix = uniqueString(resourceGroup().id)
var prefix = 'aegis${environmentName}'

// The ACR created by main.bicep. Referenced (not created) so the deploy
// workflow can read its login server for image refs + admin-cred pull secret.
resource acrExisting 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: '${prefix}acr${suffix}'
}

module aks '../modules/aks.bicep' = {
  name: 'aks'
  params: {
    name: '${prefix}-aks-${suffix}'
    location: location
    dnsPrefix: '${prefix}-aks'
    nodeCount: nodeCount
    nodeVmSize: nodeVmSize
  }
}

output clusterName string = aks.outputs.clusterName
output nodeResourceGroup string = aks.outputs.nodeResourceGroup
output oidcIssuerUrl string = aks.outputs.oidcIssuerUrl
output acrLoginServer string = acrExisting.properties.loginServer
