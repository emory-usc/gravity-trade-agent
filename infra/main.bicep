// Gravity Trade Agent — Azure infrastructure (Bicep).
//
// Deploys the full footprint the agent needs in production:
//   Container Apps (compute) + user-assigned managed identity
//   Key Vault (secrets, RBAC + purge-protected)
//   Cosmos DB (serverless; signal/thesis history)
//   Log Analytics + Application Insights (observability)
//   A CPU health alert (action group)
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
// Key Vault — holds the OpenAI API key (read via managed identity)
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
// Cosmos DB (serverless) — signal history + trade theses
// ---------------------------------------------------------------------------
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: '${namePrefix}-cosmos'
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    capabilities: [ { name: 'EnableServerless' } ]
    locations: [ { locationName: location, failoverPriority: 0 } ]
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
// Container Apps environment + app
// ---------------------------------------------------------------------------
resource containerEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: '${namePrefix}-env'
  location: location
  properties: {
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
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
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
// Alerting — action group + a CPU health alert
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

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
output appUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output vaultUri string = keyVault.properties.vaultUri
output cosmosEndpoint string = cosmos.properties.documentEndpoint
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output identityClientId string = identity.properties.clientId
