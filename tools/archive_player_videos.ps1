param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d{3}$')]
    [string]$Player,

    [Parameter(Mandatory = $true)]
    [string]$Source,

    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$destination = Join-Path $repoRoot "data\player_videos\$Player"

if (-not (Test-Path -LiteralPath $sourcePath -PathType Container)) {
    throw "Source directory not found: $sourcePath"
}

New-Item -ItemType Directory -Force -Path $destination | Out-Null

$videos = @(Get-ChildItem -LiteralPath $sourcePath -File -Recurse | Where-Object {
    $_.Extension -match '^\.(mov|mp4|m4v|avi|mkv)$'
})

if ($videos.Count -eq 0) {
    throw "No video files found in $sourcePath"
}

foreach ($video in $videos) {
    Copy-Item -LiteralPath $video.FullName -Destination (Join-Path $destination $video.Name) -Force
}

git -C $repoRoot add -- "data/player_videos/$Player"
git -C $repoRoot commit -m "Archive player $Player capture videos"

if (-not $NoPush) {
    git -C $repoRoot push v2 codex/software-data
}

Write-Host "Archived $($videos.Count) video(s) for player $Player."
