// Gravity Trade Agent — Azure infrastructure (Bicep).
//
// Deploys the full, network-isolated footprint the agent needs in production:
//   Container Apps (compute) + user-assigned managed identity, scale-to-zero
//   Key Vault (secrets, RBAC + purge-protected, private endpoint only)
//   Cosmos DB (serverless, private endpoint only)
//   VNet + subnets (app egress + private endpoints) + private DNS zones
//   Log Analytics + Application Insights (observability)
//   Alert rules (CPU health + scan-error log alert)
//
// Deploy:
//   az deployment group create --resource-group <rg> \
//     --template-file infra/main.bicep --parameters containerImage=<image>

@description('Azure region for all resources')
param location string = 'westus3'

@description('Lowercase alphanumeric prefix used for resource names')
param namePrefix string = 'gravitytrade'

@description('Container image to deploy (e.g. ghcr.io/<user>/gravity-trade-agent:latest)')
param containerImage string

@description('Email address for alert notifications (empty disables)')
param alertEmail string = ''

// ---------------------------------------------------------------------------
// Observability — Log Analytics workspace + Application Insights
// ---------------------------------------------------------------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: '${namePrefix}-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-appi'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ---------------------------------------------------------------------------
// Key Vault — holds the OpenAI + service API keys (read via managed identity).
// Network-isolated: private endpoint only (publicNetworkAccess disabled).
// ---------------------------------------------------------------------------
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${namePrefix}-kv'
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enablePurgeProtection: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Disabled'
  }
}

// ---------------------------------------------------------------------------
// User-assigned managed identity for the container app
// ---------------------------------------------------------------------------
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${namePrefix}-identity'
  location: location
}

// ---------------------------------------------------------------------------
// Cosmos DB (serverless) — signal history + trade theses. Private endpoint only.
// ---------------------------------------------------------------------------
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: '${namePrefix}-cosmos'
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    capabilities: [ { name: 'EnableServerless' } ]
    locations: [ { locationName: location, failoverPriority: 0 } ]
    publicNetworkAccess: 'Disabled'
  }
}

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmos
  name: 'gravitytrade'
  properties: {
    resource: { id: 'gravitytrade' }
  }
}

resource cosmosContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDb
  name: 'signals'
  properties: {
    resource: {
      id: 'signals'
      partitionKey: { paths: [ '/ticker' ], kind: 'Hash' }
    }
  }
}

// ---------------------------------------------------------------------------
// VNet + subnets — app egress subnet + private-endpoint subnet
// ---------------------------------------------------------------------------
resource vnet 'Microsoft.Network/virtualNetworks@2023-04-01' = {
  name: '${namePrefix}-vnet'
  location: location
  properties: {
    addressSpace: { addressPrefixes: [ '10.0.0.0/16' ] }
  }
}

resource infraSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-04-01' = {
  parent: vnet
  name: 'containerapps'
  properties: {
    addressPrefix: '10.0.1.0/24'
    delegations: [
      { name: 'Microsoft.App.environments', properties: { serviceName: 'Microsoft.App/environments' } }
    ]
  }
}

resource endpointsSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-04-01' = {
  parent: vnet
  name: 'endpoints'
  properties: {
    addressPrefix: '10.0.2.0/24'
    privateEndpointNetworkPolicies: 'Disabled'
  }
}

// ---------------------------------------------------------------------------
// Private endpoints for Key Vault + Cosmos
// ---------------------------------------------------------------------------
resource kvPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-04-01' = {
  name: '${namePrefix}-kv-pe'
  location: location
  properties: {
    subnet: { id: endpointsSubnet.id }
    privateLinkServiceConnections: [
      {
        name: '${namePrefix}-kv-plc'
        properties: {
          privateLinkServiceId: keyVault.id
          groupIds: [ 'vault' ]
        }
      }
    ]
  }
}

resource cosmosPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-04-01' = {
  name: '${namePrefix}-cosmos-pe'
  location: location
  properties: {
    subnet: { id: endpointsSubnet.id }
    privateLinkServiceConnections: [
      {
        name: '${namePrefix}-cosmos-plc'
        properties: {
          privateLinkServiceId: cosmos.id
          groupIds: [ 'Sql' ]
        }
      }
    ]
  }
}

// ---------------------------------------------------------------------------
// Private DNS zones + VNet links + A records
// ---------------------------------------------------------------------------
resource kvDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.vaultcore.azure.net'
  location: 'global'
}

resource kvDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: kvDnsZone
  name: vnet.name
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

resource kvDnsRecord 'Microsoft.Network/privateDnsZones/A@2020-06-01' = {
  parent: kvDnsZone
  name: keyVault.name
  properties: {
    ttl: 3600
    aRecords: [
      { ipv4Address: kvPrivateEndpoint.properties.customDnsConfigs[0].ipAddresses[0] }
    ]
  }
}

resource cosmosDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.documents.azure.com'
  location: 'global'
}

resource cosmosDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: cosmosDnsZone
  name: vnet.name
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

// Note: Cosmos SQL accounts may also need per-region A records; the primary
// account record below covers the common single-region case.
resource cosmosDnsRecord 'Microsoft.Network/privateDnsZones/A@2020-06-01' = {
  parent: cosmosDnsZone
  name: cosmos.name
  properties: {
    ttl: 3600
    aRecords: [
      { ipv4Address: cosmosPrivateEndpoint.properties.customDnsConfigs[0].ipAddresses[0] }
    ]
  }
}

// ---------------------------------------------------------------------------
// Container Apps environment + app (VNet-integrated, scale-to-zero)
// ---------------------------------------------------------------------------
resource containerEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: '${namePrefix}-env'
  location: location
  properties: {
    vnetConfiguration: {
      infrastructureSubnetId: infraSubnet.id
      internal: false
    }
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: '${namePrefix}-app'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
      }
    }
    template: {
      containers: [
        {
          name: 'gravity-trade-agent'
          image: containerImage
          env: [
            { name: 'AZURE_KEY_VAULT_URL', value: keyVault.properties.vaultUri }
            { name: 'COSMOS_ENDPOINT', value: cosmos.properties.documentEndpoint }
            { name: 'COSMOS_DB', value: 'gravitytrade' }
            { name: 'COSMOS_CONTAINER', value: 'signals' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8080 }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: { path: '/ready', port: 8080 }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: { concurrentRequests: '10' }
            }
          }
        ]
      }
    }
  }
}

// ---------------------------------------------------------------------------
// RBAC — grant the app identity access to Key Vault secrets + Cosmos data
// ---------------------------------------------------------------------------
resource kvRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, identity.id, 'secrets-user')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource cosmosRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cosmos.id, identity.id, 'data-contributor')
  scope: cosmos
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '00000000-0000-0000-0000-000000000002') // Cosmos DB Built-in Data Contributor
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------------------------------------------------------------------
// Alerting — action group, CPU health alert, scan-error log alert
// ---------------------------------------------------------------------------
resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: '${namePrefix}-alerts'
  location: 'Global'
  properties: {
    groupShortName: 'gravity'
    enabled: true
    emailReceivers: alertEmail != '' ? [ { name: 'oncall', emailAddress: alertEmail } ] : []
  }
}

resource cpuAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${namePrefix}-cpu-high'
  location: 'global'
  properties: {
    description: 'Container app CPU above 90% for 5 minutes'
    severity: 2
    enabled: true
    scopes: [ containerApp.id ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'CPU high'
          metricName: 'CpuPercentage'
          metricNamespace: 'Microsoft.App/containerApps'
          operator: 'GreaterThan'
          threshold: 90
          timeAggregation: 'Average'
        }
      ]
    }
    actions: alertEmail != '' ? [ { actionGroupId: actionGroup.id } ] : []
  }
}

resource errorAlert 'Microsoft.Insights/scheduledQueryRules@2021-08-01' = {
  name: '${namePrefix}-scan-errors'
  location: location
  properties: {
    description: 'Gravity Trade scan errors in the last 15 minutes'
    severity: 1
    enabled: true
    evaluationFrequency: 'PT15M'
    scopes: [ appInsights.id ]
    windowSize: 'PT15M'
    criteria: {
      allOf: [
        {
          query: 'traces | where severityLevel >= 3 | summarize Count = count() by bin(timestamp, 5m)'
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    autoMitigate: true
    actions: {
      actionGroups: [ actionGroup.id ]
    }
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output appUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output vaultUri string = keyVault.properties.vaultUri
output cosmosEndpoint string = cosmos.properties.documentEndpoint
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output identityClientId string = identity.properties.clientId
