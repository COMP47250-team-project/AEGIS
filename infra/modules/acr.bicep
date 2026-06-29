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
    // Admin user lets the Container Apps pull images using registry
    // credentials (AEGIS-66) without needing an RBAC role assignment —
    // role assignments aren't available to a guest on this subscription.
    adminUserEnabled: true
  }
}

output loginServer string = acr.properties.loginServer
output name string = acr.name
