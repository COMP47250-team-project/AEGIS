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
    // Disabled here — AEGIS-63's Container Apps run public placeholder images,
    // so no registry auth is needed yet. AEGIS-66 wires real-image pulls using
    // the Container Apps' managed identity (+ AcrPull) when it deploys them.
    adminUserEnabled: false
  }
}

output loginServer string = acr.properties.loginServer
output name string = acr.name
