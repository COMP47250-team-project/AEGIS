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
      secrets: [
        for s in keyVaultSecrets: {
          name: s.secretName
          keyVaultUrl: s.keyVaultUrl
          identity: 'system'
        }
      ]
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
