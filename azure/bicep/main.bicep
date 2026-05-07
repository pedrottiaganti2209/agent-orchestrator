// Infraestrutura completa para migração de mainframe no Azure
// Provisiona: AKS, ACR, Redis, Cosmos DB, App Insights, Key Vault

targetScope = 'resourceGroup'

@description('Ambiente de deploy: dev, homolog, prod')
@allowed(['dev', 'homolog', 'prod'])
param environment string = 'dev'

@description('Região Azure')
param location string = resourceGroup().location

@description('Sufixo único para evitar conflitos de nomes globais')
param uniqueSuffix string = uniqueString(resourceGroup().id)

var prefix = 'migration-${environment}'
var aksName = '${prefix}-aks'
var acrName = 'migration${environment}${uniqueSuffix}'
var redisName = '${prefix}-redis'
var cosmosName = '${prefix}-cosmos'
var appInsightsName = '${prefix}-insights'
var keyVaultName = '${prefix}-kv-${uniqueSuffix}'
var logWorkspaceName = '${prefix}-logs'

// Log Analytics Workspace (base para App Insights e AKS monitoring)
resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logWorkspaceName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 90
  }
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logWorkspace.id
    RetentionInDays: 90
  }
}

// Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
  }
}

// ACR com geo-replicação para prod
module acr 'modules/acr.bicep' = {
  name: 'acr-deploy'
  params: {
    name: acrName
    location: location
    environment: environment
  }
}

// AKS Cluster
module aks 'modules/aks.bicep' = {
  name: 'aks-deploy'
  params: {
    name: aksName
    location: location
    logWorkspaceId: logWorkspace.id
    appInsightsConnectionString: appInsights.properties.ConnectionString
  }
}

// Azure Cache for Redis (Premium para persistência)
module redis 'modules/redis.bicep' = {
  name: 'redis-deploy'
  params: {
    name: redisName
    location: location
    environment: environment
  }
}

// Cosmos DB
module cosmos 'modules/cosmos.bicep' = {
  name: 'cosmos-deploy'
  params: {
    name: cosmosName
    location: location
  }
}

// Armazenar connection strings no Key Vault
resource redisSecret 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = {
  parent: keyVault
  name: 'redis-connection-string'
  properties: {
    value: redis.outputs.connectionString
  }
}

resource cosmosSecret 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = {
  parent: keyVault
  name: 'cosmos-key'
  properties: {
    value: cosmos.outputs.primaryKey
  }
}

resource appInsightsSecret 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = {
  parent: keyVault
  name: 'appinsights-connection-string'
  properties: {
    value: appInsights.properties.ConnectionString
  }
}

output aksClusterName string = aksName
output acrLoginServer string = acr.outputs.loginServer
output cosmosEndpoint string = cosmos.outputs.endpoint
output keyVaultUri string = keyVault.properties.vaultUri
output appInsightsConnectionString string = appInsights.properties.ConnectionString
