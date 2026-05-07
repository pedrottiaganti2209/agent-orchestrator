// Módulo Bicep para Azure Cosmos DB com API NoSQL

param name string
param location string

@description('Regiões de replicação adicionais')
param additionalLocations array = []

var locations = concat(
  [{ locationName: location, failoverPriority: 0, isZoneRedundant: true }],
  additionalLocations
)

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: name
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: locations
    enableAutomaticFailover: true
    enableMultipleWriteLocations: false
    capabilities: []
    backupPolicy: {
      type: 'Continuous'
      continuousModeProperties: { tier: 'Continuous30Days' }
    }
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  parent: cosmos
  name: 'migration-db'
  properties: {
    resource: { id: 'migration-db' }
    options: { throughput: 400 }
  }
}

resource container 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: database
  name: 'migration-history'
  properties: {
    resource: {
      id: 'migration-history'
      partitionKey: { paths: ['/execution_id'], kind: 'Hash' }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          { path: '/module_name/?' }
          { path: '/status/?' }
          { path: '/completed_at/?' }
        ]
        excludedPaths: [{ path: '/*' }]
      }
      defaultTtl: 7776000
    }
  }
}

output endpoint string = cosmos.properties.documentEndpoint
output primaryKey string = cosmos.listKeys().primaryMasterKey
