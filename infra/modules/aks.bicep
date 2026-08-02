// AKS module — a small managed cluster for the Kubernetes/Helm deployment track.
// Sits ALONGSIDE the Container Apps deployment (infra/main.bicep); it does not
// replace it. Authored for a later live deploy; validated with `az bicep build`.
//
// Ingress: the Application Routing add-on (managed NGINX) is enabled here, so
// the Helm chart's AKS values use ingressClassName "webapprouting.kubernetes.io".
@description('Managed cluster name.')
param name string
param location string

@description('DNS prefix for the cluster API server (defaults to the name).')
param dnsPrefix string = name

@description('Node count for the system node pool.')
param nodeCount int = 2

@description('Node VM size. Standard_B2s is a low-cost burstable size adequate for a demo cluster.')
param nodeVmSize string = 'Standard_B2s'

@description('Kubernetes version. Empty string lets AKS pick the current default.')
param kubernetesVersion string = ''

resource aks 'Microsoft.ContainerService/managedClusters@2024-05-01' = {
  name: name
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    dnsPrefix: dnsPrefix
    kubernetesVersion: empty(kubernetesVersion) ? null : kubernetesVersion
    agentPoolProfiles: [
      {
        name: 'system'
        mode: 'System'
        count: nodeCount
        vmSize: nodeVmSize
        osType: 'Linux'
        osSKU: 'Ubuntu'
        type: 'VirtualMachineScaleSets'
      }
    ]
    // Application Routing add-on: Azure-managed NGINX ingress controller.
    // Avoids self-managing an ingress-nginx Helm release on the cluster.
    ingressProfile: {
      webAppRouting: {
        enabled: true
      }
    }
    // Workload Identity + OIDC issuer — lets future workloads federate to Azure
    // AD without secrets (e.g. Key Vault CSI). Authored now for the roadmap.
    oidcIssuerProfile: {
      enabled: true
    }
    securityProfile: {
      workloadIdentity: {
        enabled: true
      }
    }
  }
}

// NOTE: no AcrPull role assignment here. Attaching ACR (az aks --attach-acr, or
// a Microsoft.Authorization/roleAssignments AcrPull grant) requires role-
// assignment write, which the sponsored-subscription guest accounts are denied
// (same constraint documented in infra/modules/acr.bicep). Instead the deploy
// workflow creates a docker-registry imagePullSecret from ACR admin creds, and
// the Helm chart references it via imagePullSecrets.

output clusterName string = aks.name
output nodeResourceGroup string = aks.properties.nodeResourceGroup
output oidcIssuerUrl string = aks.properties.oidcIssuerProfile.issuerURL
output kubeletIdentityObjectId string = aks.properties.identityProfile.kubeletidentity.objectId
