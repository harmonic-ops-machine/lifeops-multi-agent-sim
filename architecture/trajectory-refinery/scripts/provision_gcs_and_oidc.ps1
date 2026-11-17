<#
.SYNOPSIS
  Stage-gated provisioning script for the Trajectory Refinery GCS Bronze Bucket
  and Keyless GitHub Actions OIDC Workload Identity Federation (`v8.3.1`).

.DESCRIPTION
  Defaults to DryRun ($Apply = $false) in accordance with HIGHRES stage-gated
  infrastructure governance. Validates all inputs, avoids Invoke-Expression,
  scopes OIDC trust to a single GitHub repository, provisions a least-privilege
  service account, and enforces CLOUDSDK_METRICS_ENVIRONMENT attribution.
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[a-z][a-z0-9-]{4,29}$")]
    [string]$ProjectId,

    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[a-z0-9][a-z0-9._-]{2,62}$")]
    [string]$BucketName,

    [ValidatePattern("^[A-Za-z0-9-]+$")]
    [string]$Location = "US-CENTRAL1",

    [ValidatePattern("^[A-Za-z0-9-]+$")]
    [string]$GitHubOwner = "harmonic-ops-machine",

    [ValidatePattern("^[A-Za-z0-9._-]+$")]
    [string]$GitHubRepo = "gemini-session-refinery",

    [ValidatePattern("^[a-z0-9-]{4,32}$")]
    [string]$WorkloadPoolId = "github-harmonic-ops-pool",

    [ValidatePattern("^[a-z0-9-]{4,32}$")]
    [string]$WorkloadProviderId = "github-oidc-provider",

    [ValidatePattern("^[a-z][a-z0-9-]{5,29}$")]
    [string]$ServiceAccountId = "sa-trajectory-refinery",

    [ValidatePattern("^[0-9]*$")]
    [string]$ProjectNumber = "",

    [switch]$Apply
)

$ErrorActionPreference = "Stop"

# Enforce mandatory Data Agent Kit / Antigravity Cloud SDK attribution
$env:CLOUDSDK_METRICS_ENVIRONMENT = if ($env:CLOUDSDK_METRICS_ENVIRONMENT) {
    "$env:CLOUDSDK_METRICS_ENVIRONMENT datacloud.antigravity"
} else {
    "datacloud.antigravity"
}

$resolvedProjectNumber = $ProjectNumber
if ($Apply -and [string]::IsNullOrWhiteSpace($resolvedProjectNumber)) {
    $resolvedProjectNumber = (& gcloud projects describe $ProjectId --format="value(projectNumber)").Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($resolvedProjectNumber)) {
        throw "Failed to resolve numeric projectNumber for project '$ProjectId'."
    }
}
if ([string]::IsNullOrWhiteSpace($resolvedProjectNumber)) {
    $resolvedProjectNumber = "<PROJECT_NUMBER>"
}

$atSign = [char]64
$saPrincipal = "$ServiceAccountId$atSign$ProjectId.iam.gserviceaccount.com"
$repoFull = "$GitHubOwner/$GitHubRepo"
$wifPrincipalSet = "principalSet://iam.googleapis.com/projects/$resolvedProjectNumber/locations/global/workloadIdentityPools/$WorkloadPoolId/attribute.repository/$repoFull"

$steps = @(
    @{
        Label = "Create private GCS Bronze bucket"
        Args  = @(
            "storage", "buckets", "create", "gs://$BucketName",
            "--project=$ProjectId",
            "--location=$Location",
            "--uniform-bucket-level-access",
            "--public-access-prevention",
            "--soft-delete-duration=30d"
        )
    },
    @{
        Label = "Enable GCS Object Versioning"
        Args  = @(
            "storage", "buckets", "update", "gs://$BucketName",
            "--project=$ProjectId",
            "--versioning"
        )
    },
    @{
        Label = "Create Workload Identity Pool"
        Args  = @(
            "iam", "workload-identity-pools", "create", $WorkloadPoolId,
            "--project=$ProjectId",
            "--location=global",
            "--display-name=GitHub harmonic-ops-machine Pool"
        )
    },
    @{
        Label = "Create repository-scoped GitHub OIDC provider"
        Args  = @(
            "iam", "workload-identity-pools", "providers", "create-oidc", $WorkloadProviderId,
            "--project=$ProjectId",
            "--location=global",
            "--workload-identity-pool=$WorkloadPoolId",
            "--issuer-uri=https://token.actions.githubusercontent.com",
            "--attribute-mapping=google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner",
            "--attribute-condition=assertion.repository == '$repoFull'"
        )
    },
    @{
        Label = "Create least-privilege Trajectory Refinery Service Account"
        Args  = @(
            "iam", "service-accounts", "create", $ServiceAccountId,
            "--project=$ProjectId",
            "--display-name=Trajectory Refinery Ingestor"
        )
    },
    @{
        Label = "Grant bucket-scoped storage.objectUser to Service Account"
        Args  = @(
            "storage", "buckets", "add-iam-policy-binding", "gs://$BucketName",
            "--project=$ProjectId",
            "--member=serviceAccount:$saPrincipal",
            "--role=roles/storage.objectUser"
        )
    },
    @{
        Label = "Bind GitHub OIDC repository principalSet to Service Account"
        Args  = @(
            "iam", "service-accounts", "add-iam-policy-binding", $saPrincipal,
            "--project=$ProjectId",
            "--role=roles/iam.workloadIdentityUser",
            "--member=$wifPrincipalSet"
        )
    }
)

Write-Output "=== TRAJECTORY REFINERY PROVISIONING PLAN (Apply=$Apply) ==="
Write-Output "Attribution     : CLOUDSDK_METRICS_ENVIRONMENT=$($env:CLOUDSDK_METRICS_ENVIRONMENT)"
Write-Output "Target Repo     : $repoFull"
Write-Output "Service Account : $saPrincipal"
Write-Output "Target GCS      : gs://$BucketName ($Location, versioning=ON, soft-delete=30d, public=BLOCKED)"
Write-Output ""

foreach ($step in $steps) {
    $rendered = "gcloud " + (($step.Args | ForEach-Object {
        if ($_ -match "\s|'") { "`"$_`"" } else { $_ }
    }) -join " ")
    if ($Apply) {
        Write-Output "[EXECUTE] $($step.Label): $rendered"
        & gcloud @($step.Args)
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed during '$($step.Label)' with exit code $LASTEXITCODE."
        }
    } else {
        Write-Output "[DRY-RUN] $($step.Label): $rendered"
    }
}
