// AEGIS-63 — generic Container App (reused for backend + frontend).
@description('Container App name.')
param name string
param location string
param environmentId string

@description('Container image. Defaults are public placeholders so the first deploy succeeds before CI has pushed real images to ACR (AEGIS-66 swaps these in).')
param image string

@description('vCPU cores, e.g. "0.5".')
param cpu string

@description('Memory, e.g. "1Gi".')
param memory string

param minReplicas int = 1
param maxReplicas int = 3
param targetPort int

@description('Key Vault-backed secrets injected as env vars (AEGIS-77). Each item: { secretName, keyVaultUrl, envVarName }. The app reads them via its system-assigned identity.')
param keyVaultSecrets array = []

@description('ACR login server for pulling private images (empty = public image, no registry auth). AEGIS-66.')
param registryServer string = ''

@description('ACR admin username for image pull.')
param registryUsername string = ''

@secure()
@description('ACR admin password for image pull.')
param registryPassword string = ''

// Key Vault-backed secrets (read via managed identity) + the ACR admin password
// (a plain-value secret) when pulling private images.
var kvSecrets = [
  for s in keyVaultSecrets: {
    name: s.secretName
    keyVaultUrl: s.keyVaultUrl
    identity: 'system'
  }
]
var registrySecrets = empty(registryServer)
  ? []
  : [
      {
        name: 'acr-password'
        value: registryPassword
      }
    ]

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
      }
      registries: empty(registryServer)
        ? []
        : [
            {
              server: registryServer
              username: registryUsername
              passwordSecretRef: 'acr-password'
            }
          ]
      secrets: concat(registrySecrets, kvSecrets)
    }
    template: {
      containers: [
        {
          name: name
          image: image
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: [
            for s in keyVaultSecrets: {
              name: s.envVarName
              secretRef: s.secretName
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

output fqdn string = app.properties.configuration.ingress.fqdn
output principalId string = app.identity.principalId
