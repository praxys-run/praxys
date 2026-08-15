targetScope = 'resourceGroup'

param location string = resourceGroup().location
param image string
@secure()
param databaseUrl string
@secure()
param statsigSdkKey string
param statsigEnv string = 'production'
param logAnalyticsWorkspaceName string
param backendAppInsightsName string
param actionGroupName string = 'praxys-feedback-ag'
param queueName string = 'labs-environment-response'
param environmentName string = 'cae-praxys-jobs'
param jobName string = 'praxys-labs-environment-worker'
param identityName string = 'id-praxys-labs-worker'
param namespaceName string = 'sb-praxys-labs-${uniqueString(subscription().id)}'

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: backendAppInsightsName
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' existing = {
  name: actionGroupName
}

resource serviceBus 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: namespaceName
  location: location
  tags: {
    praxysComponent: 'labs-analysis'
  }
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  properties: {
    disableLocalAuth: true
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}

resource queue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = {
  parent: serviceBus
  name: queueName
  properties: {
    deadLetteringOnMessageExpiration: true
    defaultMessageTimeToLive: 'P14D'
    lockDuration: 'PT5M'
    // Analysis attempts are capped in PostgreSQL at three. Extra transport
    // deliveries leave room for temporary claim/settlement failures.
    maxDeliveryCount: 10
  }
}

resource workerIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

resource environment 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: environmentName
  location: location
  tags: {
    praxysComponent: 'labs-analysis'
  }
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspace.properties.customerId
        sharedKey: workspace.listKeys().primarySharedKey
      }
    }
  }
}

resource worker 'Microsoft.App/jobs@2025-01-01' = {
  name: jobName
  location: location
  tags: {
    praxysComponent: 'labs-analysis'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${workerIdentity.id}': {}
    }
  }
  properties: {
    environmentId: environment.id
    configuration: {
      triggerType: 'Event'
      replicaRetryLimit: 0
      replicaTimeout: 1800
      secrets: [
        {
          name: 'database-url'
          value: databaseUrl
        }
        {
          name: 'statsig-sdk-key'
          value: statsigSdkKey
        }
      ]
      eventTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
        scale: {
          minExecutions: 0
          maxExecutions: 1
          pollingInterval: 30
          rules: [
            {
              name: 'service-bus'
              type: 'azure-servicebus'
              identity: workerIdentity.id
              metadata: {
                namespace: serviceBus.name
                queueName: queue.name
                messageCount: '1'
              }
              auth: []
            }
          ]
        }
      }
    }
    template: {
      containers: [
        {
          name: 'labs-worker'
          image: image
          resources: {
            cpu: 1
            memory: '2Gi'
          }
          env: [
            {
              name: 'PRAXYS_DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              name: 'PRAXYS_DB_AUTH'
              value: 'entra'
            }
            {
              name: 'PRAXYS_DB_POOL_SIZE'
              value: '1'
            }
            {
              name: 'PRAXYS_DB_MAX_OVERFLOW'
              value: '1'
            }
            {
              name: 'PRAXYS_SKIP_MIGRATIONS'
              value: 'true'
            }
            {
              name: 'PRAXYS_HIDE_SQL_PARAMETERS'
              value: 'true'
            }
            {
              name: 'PRAXYS_LABS_EXECUTION_MODE'
              value: 'service_bus'
            }
            {
              name: 'STATSIG_SDK_KEY'
              secretRef: 'statsig-sdk-key'
            }
            {
              name: 'STATSIG_ENV'
              value: statsigEnv
            }
            {
              name: 'PRAXYS_LABS_SERVICE_BUS_FQDN'
              value: '${serviceBus.name}.servicebus.windows.net'
            }
            {
              name: 'PRAXYS_LABS_SERVICE_BUS_QUEUE'
              value: queue.name
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: workerIdentity.properties.clientId
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsights.properties.ConnectionString
            }
            {
              name: 'PYTHONUNBUFFERED'
              value: '1'
            }
          ]
        }
      ]
    }
  }
}

resource backlogAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'praxys-labs-queue-backlog'
  location: 'global'
  properties: {
    description: 'Labs analysis queue averaged above two active messages for 30 minutes.'
    severity: 2
    enabled: true
    scopes: [
      serviceBus.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT30M'
    autoMitigate: true
    targetResourceType: 'Microsoft.ServiceBus/namespaces'
    targetResourceRegion: location
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'LabsQueueBacklog'
          metricNamespace: 'Microsoft.ServiceBus/namespaces'
          metricName: 'ActiveMessages'
          operator: 'GreaterThan'
          threshold: 2
          timeAggregation: 'Average'
          dimensions: [
            {
              name: 'EntityName'
              operator: 'Include'
              values: [
                queue.name
              ]
            }
          ]
          skipMetricValidation: false
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

resource deadLetterAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'praxys-labs-dead-lettered'
  location: 'global'
  properties: {
    description: 'At least one Labs analysis message is in the dead-letter queue.'
    severity: 2
    enabled: true
    scopes: [
      serviceBus.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    autoMitigate: true
    targetResourceType: 'Microsoft.ServiceBus/namespaces'
    targetResourceRegion: location
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'LabsDeadLettered'
          metricNamespace: 'Microsoft.ServiceBus/namespaces'
          metricName: 'DeadletteredMessages'
          operator: 'GreaterThan'
          threshold: 0
          timeAggregation: 'Maximum'
          dimensions: [
            {
              name: 'EntityName'
              operator: 'Include'
              values: [
                queue.name
              ]
            }
          ]
          skipMetricValidation: false
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

output serviceBusNamespaceName string = serviceBus.name
output serviceBusFqdn string = '${serviceBus.name}.servicebus.windows.net'
output queueName string = queue.name
output workerIdentityClientId string = workerIdentity.properties.clientId
output workerIdentityPrincipalId string = workerIdentity.properties.principalId
output workerIdentityResourceId string = workerIdentity.id
output workerJobName string = worker.name
output queueResourceId string = queue.id
output appInsightsResourceId string = appInsights.id
