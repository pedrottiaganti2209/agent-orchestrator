// Módulo Bicep para Azure Kubernetes Service

param name string
param location string
param logWorkspaceId string
param appInsightsConnectionString string

@description('Tamanho das VMs do node pool principal')
param nodeVmSize string = 'Standard_D4s_v3'

@description('Número inicial de nós')
param nodeCount int = 3

resource aks 'Microsoft.ContainerService/managedClusters@2024-01-01' = {
  name: name
  location: location
  identity: { type: 'SystemAssigned' }
  properties: {
    kubernetesVersion: '1.29'
    dnsPrefix: name
    enableRBAC: true
    agentPoolProfiles: [
      {
        name: 'system'
        count: nodeCount
        vmSize: nodeVmSize
        osType: 'Linux'
        mode: 'System'
        enableAutoScaling: true
        minCount: 2
        maxCount: 10
        nodeTaints: []
        availabilityZones: ['1', '2', '3']
      }
      {
        name: 'migration'
        count: 2
        vmSize: nodeVmSize
        osType: 'Linux'
        mode: 'User'
        enableAutoScaling: true
        minCount: 1
        maxCount: 20
        nodeTaints: ['workload=migration:NoSchedule']
        nodeLabels: { workload: 'migration' }
        availabilityZones: ['1', '2', '3']
      }
    ]
    addonProfiles: {
      omsagent: {
        enabled: true
        config: { logAnalyticsWorkspaceResourceID: logWorkspaceId }
      }
      azureKeyVaultSecretsProvider: {
        enabled: true
        config: { enableSecretRotation: 'true', rotationPollInterval: '2m' }
      }
    }
    oidcIssuerProfile: { enabled: true }
    securityProfile: {
      workloadIdentity: { enabled: true }
    }
    networkProfile: {
      networkPlugin: 'azure'
      networkPolicy: 'azure'
      loadBalancerSku: 'standard'
    }
  }
}

output clusterName string = aks.name
output kubeletIdentityObjectId string = aks.properties.identityProfile.kubeletidentity.objectId
