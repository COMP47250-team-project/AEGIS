// AEGIS-77 — Azure Key Vault for production secrets (access-policy model).
//
// RBAC isn't used because the deploying account is a guest on the sponsored
// subscription and can't create role assignments. Access policies are part of
// the vault resource, so a Contributor can grant access without RBAC writes.
@description('Key Vault name (3-24 chars, globally unique).')
param name string
param location string
param tenantId string

@description('Object ID of the deploying user — full secret management (get/list/set/delete).')
param deployerObjectId string = ''

@description('Principal IDs (e.g. Container App managed identities) granted secret get/list.')
param readerPrincipalIds array = []

var deployerPolicies = empty(deployerObjectId)
  ? []
  : [
      {
        tenantId: tenantId
        objectId: deployerObjectId
        permissions: {
          secrets: ['get', 'list', 'set', 'delete']
        }
      }
    ]

var readerPolicies = [
  for pid in readerPrincipalIds: {
    tenantId: tenantId
    objectId: pid
    permissions: {
      secrets: ['get', 'list']
    }
  }
]

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenantId
    enableRbacAuthorization: false
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    accessPolicies: concat(deployerPolicies, readerPolicies)
  }
}

output vaultUri string = vault.properties.vaultUri
output vaultName string = vault.name
