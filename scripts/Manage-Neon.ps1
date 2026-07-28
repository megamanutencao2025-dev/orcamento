#Requires -Version 5.1

<#
.SYNOPSIS
Executa tarefas administrativas no Neon sem gravar a URL no historico.

.EXAMPLE
.\scripts\Manage-Neon.ps1 -Action Backup

.EXAMPLE
.\scripts\Manage-Neon.ps1 -Action ChangePassword -Username admin
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet("Backup", "ChangePassword", "Check")]
    [string]$Action,

    [string]$Username,

    [string]$BackupDirectory,

    [string]$PythonPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory)][string]$Executable,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "O comando administrativo falhou."
    }
}

function Restore-ProcessEnvironment {
    param(
        [Parameter(Mandatory)][string]$Name,
        [AllowNull()][string]$PreviousValue
    )

    if ($null -eq $PreviousValue) {
        Remove-Item -LiteralPath "Env:$Name" -ErrorAction SilentlyContinue
    }
    else {
        [Environment]::SetEnvironmentVariable(
            $Name,
            $PreviousValue,
            "Process"
        )
    }
}

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Python nao encontrado. Informe -PythonPath."
}
$python = (Resolve-Path -LiteralPath $PythonPath).Path

if (
    $Action -eq "ChangePassword" -and
    [string]::IsNullOrWhiteSpace($Username)
) {
    throw "Informe -Username para alterar uma senha."
}

$previousDatabaseUrl = [Environment]::GetEnvironmentVariable(
    "DATABASE_URL",
    "Process"
)
$previousSslRequire = [Environment]::GetEnvironmentVariable(
    "DJANGO_DATABASE_SSL_REQUIRE",
    "Process"
)
$previousDisableCursors = [Environment]::GetEnvironmentVariable(
    "DJANGO_DB_DISABLE_SERVER_SIDE_CURSORS",
    "Process"
)
$secureUrl = $null
$urlPointer = [IntPtr]::Zero
$plainUrl = $null
$partialBackupPath = $null

Push-Location $projectRoot
try {
    $secureUrl = Read-Host (
        "Cole a URL DIRETA do Neon (sem -pooler); a entrada ficara oculta"
    ) -AsSecureString
    $urlPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR(
        $secureUrl
    )
    $plainUrl = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
        $urlPointer
    )

    $parsedUrl = $null
    if (
        -not [Uri]::TryCreate(
            $plainUrl,
            [UriKind]::Absolute,
            [ref]$parsedUrl
        ) -or
        $parsedUrl.Scheme -notin @("postgres", "postgresql") -or
        -not $parsedUrl.Host.EndsWith(
            ".neon.tech",
            [StringComparison]::OrdinalIgnoreCase
        ) -or
        $parsedUrl.Host -match "-pooler"
    ) {
        throw "Informe uma URL direta valida do Neon."
    }
    if ($parsedUrl.Query -notmatch "(^|[?&])sslmode=require(&|$)") {
        throw "A URL deve preservar o parametro sslmode=require."
    }

    $env:DATABASE_URL = $plainUrl
    $env:DJANGO_DATABASE_SSL_REQUIRE = "True"
    $env:DJANGO_DB_DISABLE_SERVER_SIDE_CURSORS = "False"
    $plainUrl = $null

    if ($Action -eq "Check") {
        Invoke-CheckedCommand `
            -Executable $python `
            -Arguments @("manage.py", "check")
        Invoke-CheckedCommand `
            -Executable $python `
            -Arguments @("manage.py", "ensure_network_admin", "--check")
        Write-Host "Conexao e administrador validados." -ForegroundColor Green
    }
    elseif ($Action -eq "ChangePassword") {
        Invoke-CheckedCommand `
            -Executable $python `
            -Arguments @("manage.py", "changepassword", $Username)
    }
    else {
        if ([string]::IsNullOrWhiteSpace($BackupDirectory)) {
            $BackupDirectory = Join-Path (
                [Environment]::GetFolderPath("MyDocuments")
            ) "GestorEletricoBackups"
        }
        $backupRoot = [IO.Path]::GetFullPath($BackupDirectory)
        $projectPrefix = $projectRoot.TrimEnd("\") + "\"
        if (
            $backupRoot.Equals(
                $projectRoot,
                [StringComparison]::OrdinalIgnoreCase
            ) -or
            $backupRoot.StartsWith(
                $projectPrefix,
                [StringComparison]::OrdinalIgnoreCase
            )
        ) {
            throw "O backup deve ficar fora do projeto."
        }
        [IO.Directory]::CreateDirectory($backupRoot) | Out-Null
        $backupName = (
            "neon-{0}-{1}.json" -f
            (Get-Date -Format "yyyyMMdd-HHmmss"),
            [Guid]::NewGuid().ToString("N")
        )
        $backupPath = Join-Path $backupRoot $backupName
        $partialBackupPath = "$backupPath.partial"
        Invoke-CheckedCommand `
            -Executable $python `
            -Arguments @(
                "manage.py",
                "export_deployment_data",
                "--output",
                $partialBackupPath
            )
        $hash = (
            Get-FileHash -LiteralPath $partialBackupPath -Algorithm SHA256
        ).Hash
        Move-Item `
            -LiteralPath $partialBackupPath `
            -Destination $backupPath `
            -ErrorAction Stop
        $partialBackupPath = $null
        Write-Host "Backup Neon criado em: $backupPath" -ForegroundColor Green
        Write-Host "SHA-256: $hash"
        Write-Warning (
            "O arquivo contem dados de clientes e hash de senha. " +
            "Mantenha-o privado."
        )
    }
}
finally {
    $environmentStates = @(
        [PSCustomObject]@{
            Name = "DATABASE_URL"
            Value = $previousDatabaseUrl
        },
        [PSCustomObject]@{
            Name = "DJANGO_DATABASE_SSL_REQUIRE"
            Value = $previousSslRequire
        },
        [PSCustomObject]@{
            Name = "DJANGO_DB_DISABLE_SERVER_SIDE_CURSORS"
            Value = $previousDisableCursors
        }
    )
    foreach ($environmentState in $environmentStates) {
        try {
            Restore-ProcessEnvironment `
                -Name $environmentState.Name `
                -PreviousValue $environmentState.Value
        }
        catch {
            Write-Warning (
                "Falha ao restaurar a variavel $($environmentState.Name). " +
                "Feche este PowerShell antes de continuar."
            )
        }
    }

    $plainUrl = $null
    if ($urlPointer -ne [IntPtr]::Zero) {
        try {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($urlPointer)
        }
        catch {
            Write-Warning "Falha ao zerar a memoria da URL do Neon."
        }
    }
    $secureUrl = $null

    if (
        -not [string]::IsNullOrWhiteSpace($partialBackupPath) -and
        (Test-Path -LiteralPath $partialBackupPath -PathType Leaf)
    ) {
        try {
            Remove-Item `
                -LiteralPath $partialBackupPath `
                -Force `
                -ErrorAction Stop
        }
        catch {
            Write-Warning (
                "Nao foi possivel apagar o backup parcial: " +
                $partialBackupPath
            )
        }
    }

    try {
        Pop-Location
    }
    catch {
        Write-Warning "Nao foi possivel restaurar o diretorio atual."
    }
}
