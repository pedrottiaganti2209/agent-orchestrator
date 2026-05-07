// Módulo Bicep para Azure Container Registry com geo-replicação em prod

param name string
param location string

@allowed(['dev', 'homolog', 'prod'])
param environment string = 'dev'

var sku = environment == 'prod' ? 'Premium' : 'Standard'

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: name
  location: location
  sku: { name: sku }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
    policies: {
      retentionPolicy: {
        status: 'enabled'
        days: 30
      }
    }
  }
}

// Geo-replicação apenas em prod (requer SKU Premium)
resource replication 'Microsoft.ContainerRegistry/registries/replications@2023-07-01' = if (environment == 'prod') {
  parent: acr
  name: 'brazilsouth'
  location: 'brazilsouth'
  properties: { regionEndpointEnabled: true }
}

output loginServer string = acr.properties.loginServer
output resourceId string = acr.id
