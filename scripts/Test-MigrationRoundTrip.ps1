#Requires -Version 5.1

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Django {
    param(
        [Parameter(Mandatory)][string]$Python,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Falha no comando Django: $($Arguments -join ' ')"
    }
}

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python do .venv nao encontrado."
}

$temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$testRoot = [IO.Path]::GetFullPath(
    (Join-Path $temporaryRoot (
        "gestor-migration-test-" + [Guid]::NewGuid().ToString("N")
    ))
)
if (-not $testRoot.StartsWith(
    $temporaryRoot,
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw "Diretorio temporario invalido."
}
[IO.Directory]::CreateDirectory($testRoot) | Out-Null

$fixturePath = Join-Path $testRoot "data.json"
$targetFixturePath = Join-Path $testRoot "target-data.json"
$sourceSnapshotPath = Join-Path $testRoot "source.json"
$targetSnapshotPath = Join-Path $testRoot "target.json"
$sourceBackupPath = Join-Path $testRoot "source-backup.sqlite3"
$targetDatabasePath = Join-Path $testRoot "target.sqlite3"
$temporaryPaths = @(
    $fixturePath,
    $targetFixturePath,
    $sourceSnapshotPath,
    $targetSnapshotPath,
    $sourceBackupPath,
    $targetDatabasePath
)
$previousDatabaseUrl = [Environment]::GetEnvironmentVariable(
    "DATABASE_URL",
    "Process"
)

Push-Location $projectRoot
try {
    Remove-Item -LiteralPath "Env:DATABASE_URL" -ErrorAction SilentlyContinue
    Invoke-Django `
        -Python $python `
        -Arguments @(
            "manage.py",
            "backup_sqlite_source",
            "--output",
            $sourceBackupPath
        )
    $sourceUrlPath = $sourceBackupPath.Replace("\", "/")
    $env:DATABASE_URL = "sqlite:///$sourceUrlPath"
    Invoke-Django `
        -Python $python `
        -Arguments @(
            "manage.py",
            "deployment_data_snapshot",
            "--output",
            $sourceSnapshotPath
        )
    Invoke-Django `
        -Python $python `
        -Arguments @(
            "manage.py",
            "export_deployment_data",
            "--output",
            $fixturePath
        )

    $targetUrlPath = $targetDatabasePath.Replace("\", "/")
    $env:DATABASE_URL = "sqlite:///$targetUrlPath"
    Invoke-Django `
        -Python $python `
        -Arguments @("manage.py", "migrate", "--noinput")
    Invoke-Django `
        -Python $python `
        -Arguments @(
            "manage.py",
            "assert_neon_import_target",
            "--allow-non-postgres"
        )
    Invoke-Django `
        -Python $python `
        -Arguments @("manage.py", "loaddata", $fixturePath)
    Invoke-Django `
        -Python $python `
        -Arguments @(
            "manage.py",
            "export_deployment_data",
            "--output",
            $targetFixturePath
        )
    Invoke-Django `
        -Python $python `
        -Arguments @(
            "manage.py",
            "deployment_data_snapshot",
            "--output",
            $targetSnapshotPath
        )
    Invoke-Django `
        -Python $python `
        -Arguments @("manage.py", "ensure_network_admin", "--check")

    $sourceFixtureHash = (
        Get-FileHash -LiteralPath $fixturePath -Algorithm SHA256
    ).Hash
    $targetFixtureHash = (
        Get-FileHash -LiteralPath $targetFixturePath -Algorithm SHA256
    ).Hash
    $sourceSnapshotHash = (
        Get-FileHash -LiteralPath $sourceSnapshotPath -Algorithm SHA256
    ).Hash
    $targetSnapshotHash = (
        Get-FileHash -LiteralPath $targetSnapshotPath -Algorithm SHA256
    ).Hash
    if (
        $sourceFixtureHash -ne $targetFixtureHash -or
        $sourceSnapshotHash -ne $targetSnapshotHash
    ) {
        throw "O ensaio encontrou diferencas entre origem e destino."
    }

    $snapshot = Get-Content -Raw $targetSnapshotPath | ConvertFrom-Json
    Write-Host "Ensaio de migracao concluido sem diferencas." `
        -ForegroundColor Green
    Write-Host (
        "Usuarios: {0} | Orcamentos: {1} | Unidades: {2}" -f
        $snapshot.counts."auth.User",
        $snapshot.counts."orcamentos.Orcamento",
        $snapshot.counts."cadastros.UnidadeMedida"
    )
    foreach ($quote in $snapshot.quotes) {
        Write-Host "$($quote.numero): R$ $($quote.total_final)"
    }
}
finally {
    try {
        if ($null -eq $previousDatabaseUrl) {
            Remove-Item -LiteralPath "Env:DATABASE_URL" `
                -ErrorAction SilentlyContinue
        }
        else {
            $env:DATABASE_URL = $previousDatabaseUrl
        }
    }
    catch {
        Write-Warning (
            "Falha ao restaurar DATABASE_URL. Feche este PowerShell."
        )
    }

    foreach ($temporaryPath in $temporaryPaths) {
        try {
            if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
                Remove-Item `
                    -LiteralPath $temporaryPath `
                    -Force `
                    -ErrorAction Stop
            }
        }
        catch {
            Write-Warning (
                "Nao foi possivel apagar o arquivo temporario: " +
                $temporaryPath
            )
        }
    }
    try {
        if (
            (Test-Path -LiteralPath $testRoot -PathType Container) -and
            $testRoot.StartsWith(
                $temporaryRoot,
                [StringComparison]::OrdinalIgnoreCase
            )
        ) {
            Remove-Item -LiteralPath $testRoot -ErrorAction Stop
        }
    }
    catch {
        Write-Warning "Nao foi possivel apagar o diretorio temporario."
    }
    try {
        Pop-Location
    }
    catch {
        Write-Warning "Nao foi possivel restaurar o diretorio atual."
    }
}
