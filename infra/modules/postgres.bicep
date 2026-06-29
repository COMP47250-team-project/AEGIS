// AEGIS-63 — PostgreSQL Flexible Server (Burstable Standard_B1ms, 32 GiB).
// (The ticket's "GP_Gen5" is legacy Single-Server naming; Flexible Server's
// equivalent for the 1-vCore spec is Standard_B1ms / Burstable.)
@description('Flexible Server name (globally unique).')
param name string
param location string
param administratorLogin string

@secure()
param administratorPassword string

param databaseName string = 'aegis'

resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: name
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorPassword
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: pg
  name: databaseName
}

// Allow connections from other Azure services (e.g. the Container Apps).
resource allowAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  parent: pg
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

output fqdn string = pg.properties.fullyQualifiedDomainName
output databaseName string = databaseName
