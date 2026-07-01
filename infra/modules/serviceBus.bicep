// AEGIS-63 — Service Bus Standard namespace + telemetry queue.
@description('Namespace name (globally unique).')
param name string
param location string
param queueName string = 'aegis-events'

resource namespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: name
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  identity: {
    type: 'SystemAssigned'
  }
}

resource queue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: namespace
  name: queueName
}

output namespaceName string = namespace.name
output queueName string = queueName

// Ticket requires connection strings as outputs; move to Key Vault in AEGIS-25.
#disable-next-line outputs-should-not-contain-secrets
output connectionString string = listKeys(
  resourceId('Microsoft.ServiceBus/namespaces/authorizationRules', name, 'RootManageSharedAccessKey'),
  '2022-10-01-preview'
).primaryConnectionString
