// AEGIS-63 — Azure Container Registry (Basic).
@description('Globally-unique registry name (alphanumeric, 5-50 chars).')
param name string
param location string

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: name
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    // Admin user enabled: the Container Apps pull private images using the ACR
    // admin credentials. The cleaner managed-identity + AcrPull approach needs a
    // role assignment (Microsoft.Authorization/roleAssignments/write), which the
    // sponsored-subscription guest accounts are denied — so admin auth is the
    // only workable path here. (Accepted SonarCloud hotspot.)
    #disable-next-line adminuser-should-be-disabled
    adminUserEnabled: true
  }
}

output loginServer string = acr.properties.loginServer
output name string = acr.name
