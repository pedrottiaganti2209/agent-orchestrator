// Módulo Bicep para Azure Cache for Redis Premium (com persistência)

param name string
param location string

@allowed(['dev', 'homolog', 'prod'])
param environment string = 'dev'

var skuName = environment == 'prod' ? 'Premium' : 'Standard'
var skuFamily = environment == 'prod' ? 'P' : 'C'
var skuCapacity = environment == 'prod' ? 1 : 0

resource redis 'Microsoft.Cache/redis@2023-08-01' = {
  name: name
  location: location
  properties: {
    sku: {
      name: skuName
      family: skuFamily
      capacity: skuCapacity
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    redisConfiguration: {
      // Persistência RDB habilitada apenas no SKU Premium
      'rdb-backup-enabled': environment == 'prod' ? 'true' : 'false'
      'rdb-backup-frequency': '60'
      'maxmemory-policy': 'allkeys-lru'
    }
  }
}

// Formato de connection string compatível com StackExchange.Redis e redis-py
var connectionString = '${redis.properties.hostName}:${redis.properties.sslPort},password=${redis.listKeys().primaryKey},ssl=True,abortConnect=False'

output hostName string = redis.properties.hostName
output sslPort int = redis.properties.sslPort
output connectionString string = connectionString
