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

@description('Additional user/group object IDs granted full secret management (e.g. other DevOps leads). Passed at deploy time so no IDs are committed.')
param adminObjectIds array = []

@description('Principal IDs (e.g. Container App managed identities) granted secret get/list.')
param readerPrincipalIds array = []

// Full secret management for the deployer + any additional admins.
var adminObjectIdsAll = empty(deployerObjectId) ? adminObjectIds : union([deployerObjectId], adminObjectIds)
var adminPolicies = [
  for oid in adminObjectIdsAll: {
    tenantId: tenantId
    objectId: oid
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
    accessPolicies: concat(adminPolicies, readerPolicies)
  }
}

output vaultUri string = vault.properties.vaultUri
output vaultName string = vault.name
