// Azure Communication Services: Email Communication Service + free managed domain
// + Communication Service. Provides the connection string and a sender address
// that the backend email_service.py uses for password reset and grade notifications.

@description('Base name; resources are derived from it.')
param name string

// All ACS resources use 'global' as their location; the location parameter
// is intentionally omitted to avoid the no-unused-params linter warning.

// Email Communication Service (data plane for email sending)
resource emailService 'Microsoft.Communication/emailServices@2023-04-01' = {
  name: '${name}-email'
  location: 'global'
  properties: {
    dataLocation: 'Europe'
  }
}

// Free Azure-managed domain (*.azurecomm.net) — no DNS verification needed.
resource managedDomain 'Microsoft.Communication/emailServices/domains@2023-04-01' = {
  parent: emailService
  name: 'AzureManagedDomain'
  location: 'global'
  properties: {
    domainManagement: 'AzureManaged'
  }
}

// Communication Service — ties together email + telephony (we use email only).
resource commService 'Microsoft.Communication/communicationServices@2023-04-01' = {
  name: name
  location: 'global'
  properties: {
    dataLocation: 'Europe'
    linkedDomains: [
      managedDomain.id
    ]
  }
}

#disable-next-line outputs-should-not-contain-secrets
output connectionString string = commService.listKeys().primaryConnectionString
output senderAddress string = 'DoNotReply@${managedDomain.properties.mailFromSenderDomain}'
