#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$QpsClone,

    [string]$OutDir = ".\output\r3_successor_handoff",

    [string]$SourceSha = "1248290ca0a9d55ec83d0efa0235ed1a45a88eeb",

    [switch]$SkipFetch
)

$ErrorActionPreference = "Stop"
$BundleName = "QPS_R3_1248290c.bundle"
$TmpRef = "refs/gmi/r3-exact-1248290c"

function Fail([string]$Message) {
    Write-Error "R3_SUCCESSOR_HANDOFF_FAIL: $Message"
    exit 2
}

function Invoke-Git([string[]]$GitArgs) {
    $output = & git -C $QpsClone @GitArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git $($GitArgs -join ' ') failed: $($output -join [Environment]::NewLine)"
    }
    return @($output)
}

if (-not (Test-Path -LiteralPath $QpsClone)) {
    Fail "QPS clone path does not exist: $QpsClone"
}

try {
    $inside = Invoke-Git @("rev-parse", "--is-inside-work-tree")
    if (($inside -join "").Trim() -ne "true") {
        Fail "path is not a genuine Git worktree"
    }

    $origin = (Invoke-Git @("remote", "get-url", "origin") | Select-Object -First 1).Trim()
    if ($origin -notmatch 'github\.com[:/]+GBOGEB/cryoplant-project(?:\.git)?$') {
        Fail "origin is not GBOGEB/cryoplant-project: $origin"
    }

    $branch = (Invoke-Git @("branch", "--show-current") | Select-Object -First 1).Trim()
    $headBefore = (Invoke-Git @("rev-parse", "HEAD") | Select-Object -First 1).Trim()
    $statusLines = @(Invoke-Git @("status", "--porcelain"))
    $dirty = $statusLines.Count -gt 0

    if (-not $SkipFetch) {
        Write-Host "Fetching origin/main without checkout/reset..."
        Invoke-Git @("fetch", "origin", "main", "--prune") | Out-Host
    }

    & git -C $QpsClone cat-file -e "$SourceSha^{commit}" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Fail "required successor commit is absent after fetch: $SourceSha"
    }

    $resolved = (Invoke-Git @("rev-parse", "--verify", "$SourceSha^{commit}") | Select-Object -First 1).Trim()
    if ($resolved -ne $SourceSha) {
        Fail "verified commit mismatch: expected $SourceSha observed $resolved"
    }

    $headAfterFetch = (Invoke-Git @("rev-parse", "HEAD") | Select-Object -First 1).Trim()
    if ($headAfterFetch -ne $headBefore) {
        Fail "current checkout moved unexpectedly during object fetch"
    }

    $outFull = [System.IO.Path]::GetFullPath($OutDir)
    New-Item -ItemType Directory -Path $outFull -Force | Out-Null

    $bundle = Join-Path $outFull $BundleName
    $sidecar = "$bundle.sha256"
    $receipt = Join-Path $outFull "QPS_R3_1248290c.bundle.receipt.json"

    Invoke-Git @("update-ref", $TmpRef, $SourceSha) | Out-Null
    try {
        Invoke-Git @("bundle", "create", $bundle, $TmpRef) | Out-Null
        $verifyOutput = @(& git bundle verify $bundle 2>&1)
        if ($LASTEXITCODE -ne 0) {
            Fail "git bundle verify failed"
        }

        $heads = @(& git bundle list-heads $bundle 2>&1)
        if ($LASTEXITCODE -ne 0) {
            Fail "git bundle list-heads failed"
        }
        if (-not (($heads -join [Environment]::NewLine) -match [regex]::Escape($SourceSha))) {
            Fail "bundle does not advertise required successor commit"
        }

        $sha = (Get-FileHash -LiteralPath $bundle -Algorithm SHA256).Hash.ToLowerInvariant()
        $bytes = (Get-Item -LiteralPath $bundle).Length
        [System.IO.File]::WriteAllText(
            $sidecar,
            "$sha  $BundleName" + [Environment]::NewLine,
            [System.Text.UTF8Encoding]::new($false)
        )

        $headFinal = (Invoke-Git @("rev-parse", "HEAD") | Select-Object -First 1).Trim()
        if ($headFinal -ne $headBefore) {
            Fail "current checkout moved while building bundle"
        }

        $receiptObject = [ordered]@{
            schema = "gmi.r3_successor.git_bundle_receipt.v2"
            status = "PASS_GENUINE_GIT_BUNDLE_CREATED_AND_VERIFIED"
            repository = "GBOGEB/cryoplant-project"
            required_commit = $SourceSha
            verified_commit = $resolved
            source_clone_path = (Resolve-Path -LiteralPath $QpsClone).Path
            source_clone_origin = $origin
            source_clone_branch = $branch
            source_clone_head_before = $headBefore
            source_clone_head_after = $headFinal
            source_worktree_dirty = $dirty
            source_worktree_status_entry_count = $statusLines.Count
            source_worktree_clean_required = $false
            fetch_performed = (-not $SkipFetch.IsPresent)
            checkout_or_reset_performed = $false
            worktree_mutated = $false
            bundle_filename = $BundleName
            bundle_sha256 = $sha
            bundle_bytes = [int64]$bytes
            git_bundle_verify = "PASS"
            advertised_refs = @($heads)
            verify_output = @($verifyOutput)
            connector_reconstructed_checkout = $false
            authority_transfer = $false
            formal_credit_delta = 0
        }

        $json = $receiptObject | ConvertTo-Json -Depth 8
        [System.IO.File]::WriteAllText(
            $receipt,
            $json + [Environment]::NewLine,
            [System.Text.UTF8Encoding]::new($false)
        )

        Write-Host "R3_SUCCESSOR_GIT_BUNDLE=PASS"
        Write-Host "BUNDLE=$bundle"
        Write-Host "SIDECAR=$sidecar"
        Write-Host "RECEIPT=$receipt"
        Write-Host "WORKTREE_DIRTY=$dirty (allowed; checkout was not changed)"
    }
    finally {
        & git -C $QpsClone update-ref -d $TmpRef *> $null
    }
}
catch {
    Fail $_.Exception.Message
}
