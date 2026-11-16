<#
.SYNOPSIS
  Stage-gated provisioning script for the Trajectory Refinery GCS Bronze Bucket
  and Keyless GitHub Actions OIDC Workload Identity Federation.

.DESCRIPTION
  Defaults to DryRun ($Apply = $false) in accordance with HIGHRES stage-gated
  infrastructure governance. Enforces CLOUDSDK_METRICS_ENVIRONMENT attribution.
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,

    [Parameter(Mandatory = $true)]
    [string]$BucketName,

    [string]$Location = "US-CENTRAL1",
    [string]$GitHubOwner = "harmonic-ops-machine",
    [string]$GitHubRepo = "gemini-session-refinery",
    [string]$WorkloadPoolId = "github-harmonic-ops-pool",
    [string]$WorkloadProviderId = "github-oidc-provider",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

# Enforce mandatory Data Agent Kit / Antigravity Cloud SDK attribution
$env:CLOUDSDK_METRICS_ENVIRONMENT = if ($env:CLOUDSDK_METRICS_ENVIRONMENT) {
    "$env:CLOUDSDK_METRICS_ENVIRONMENT datacloud.antigravity"
} else {
    "datacloud.antigravity"
}

$commands = @(
    # 1. Create private GCS Bronze Vault with uniform bucket-level access & public access prevention
    "gcloud storage buckets create gs://$BucketName --project=$ProjectId --location=$Location --uniform-bucket-level-access --public-access-prevention --soft-delete-duration=30d",

    # 2. Enable Object Versioning so no agent can overwrite or truncate raw session history
    "gcloud storage buckets update gs://$BucketName --project=$ProjectId --versioning",

    # 3. Create Keyless Workload Identity Pool & GitHub OIDC Provider (zero stored JSON keys)
    "gcloud iam workload-identity-pools create $WorkloadPoolId --project=$ProjectId --location=global --display-name=`"GitHub harmonic-ops-machine Pool`"",
    "gcloud iam workload-identity-pools providers create-oidc $WorkloadProviderId --project=$ProjectId --location=global --workload-identity-pool=$WorkloadPoolId --issuer-uri=`"https://token.actions.githubusercontent.com`" --attribute-mapping=`"google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner`" --attribute-condition=`"assertion.repository_owner == '$GitHubOwner'`""
)

Write-Output "=== TRAJECTORY REFINERY PROVISIONING PLAN (Apply=$Apply) ==="
Write-Output "Attribution: CLOUDSDK_METRICS_ENVIRONMENT=$($env:CLOUDSDK_METRICS_ENVIRONMENT)"
Write-Output "Target Repo: $GitHubOwner/$GitHubRepo"
Write-Output "Target GCS : gs://$BucketName ($Location, versioning=ON, soft-delete=30d, public=BLOCKED)"
Write-Output ""

foreach ($cmd in $commands) {
    if ($Apply) {
        Write-Output "[EXECUTE] $cmd"
        Invoke-Expression $cmd
    } else {
        Write-Output "[DRY-RUN] $cmd"
    }
}
