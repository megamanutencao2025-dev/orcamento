#Requires -Version 5.1

<#
.SYNOPSIS
Transfere com seguranca os dados atuais do SQLite para um Neon vazio.

.DESCRIPTION
Valida e copia o SQLite, exporta uma fixture temporaria, exige a URL direta
do Neon em prompt mascarado, bloqueia destinos ocupados, importa e compara
um retrato deterministico dos dados. Nenhuma credencial ou fixture e gravada
no repositorio.

.PARAMETER ConfirmLocalServerStopped
Confirma que Waitress/runserver foi encerrado e que ninguem gravara no SQLite.

.PARAMETER PythonPath
Caminho opcional para python.exe. Prioriza .venv\Scripts\python.exe.

.PARAMETER BackupDirectory
Diretorio externo ao projeto para a copia de seguranca do SQLite.

.EXAMPLE
.\scripts\Migrate-SqliteToNeon.ps1 -ConfirmLocalServerStopped
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [switch]$ConfirmLocalServerStopped,

    [string]$PythonPath,

    [string]$BackupDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-PythonExecutable {
    param(
        [Parameter(Mandatory)][string]$ProjectRoot,
        [string]$RequestedPath
    )

    if (-not [string]::IsNullOrWhiteSpace($RequestedPath)) {
        if (Test-Path -LiteralPath $RequestedPath -PathType Leaf) {
            return (Resolve-Path -LiteralPath $RequestedPath).Path
        }
        $requestedCommand = Get-Command $RequestedPath -ErrorAction SilentlyContinue
        if ($null -ne $requestedCommand) {
            return $requestedCommand.Source
        }
        throw "Python nao encontrado no caminho informado."
    }

    $virtualEnvironmentPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $virtualEnvironmentPython -PathType Leaf) {
        return (Resolve-Path -LiteralPath $virtualEnvironmentPython).Path
    }

    $systemPython = Get-Command "python" -ErrorAction SilentlyContinue
    if ($null -ne $systemPython) {
        return $systemPython.Source
    }
    throw "Python nao encontrado. Crie .venv ou informe -PythonPath."
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory)][string]$Description,
        [Parameter(Mandatory)][string]$Executable,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    Write-Host "$Description..." -ForegroundColor Cyan
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Falha durante: $Description."
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

function Assert-NoLocalDjangoServer {
    $servers = @()
    try {
        $servers = @(
            Get-CimInstance Win32_Process -ErrorAction Stop |
                Where-Object {
                    $_.CommandLine -match "waitress|manage\.py.+runserver" -and
                    $_.CommandLine -match "eletrico\.wsgi|manage\.py.+runserver"
                }
        )
    }
    catch {
        Write-Warning (
            "Nao foi possivel consultar todos os processos. Confirme " +
            "manualmente que o servidor local esta encerrado."
        )
    }

    if ($servers.Count -gt 0) {
        throw (
            "Foi detectado Waitress/runserver usando esta aplicacao. " +
            "Encerre o servidor local e execute novamente; nenhum processo " +
            "foi finalizado pelo script."
        )
    }
}

if (-not $ConfirmLocalServerStopped) {
    throw (
        "Encerre o servidor local e execute novamente com " +
        "-ConfirmLocalServerStopped."
    )
}

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$sqlitePath = [IO.Path]::GetFullPath(
    (Join-Path $projectRoot "database\db.sqlite3")
)
if (-not (Test-Path -LiteralPath $sqlitePath -PathType Leaf)) {
    throw "Banco SQLite nao encontrado em database\db.sqlite3."
}
Assert-NoLocalDjangoServer

$pythonExecutable = Resolve-PythonExecutable `
    -ProjectRoot $projectRoot `
    -RequestedPath $PythonPath

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
    throw "O diretorio de backup deve ficar fora do projeto."
}
[IO.Directory]::CreateDirectory($backupRoot) | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$migrationId = "$timestamp-$([Guid]::NewGuid().ToString('N'))"
$backupPath = Join-Path $backupRoot "db-$migrationId.sqlite3"
$temporaryRoot = [IO.Path]::GetTempPath()
$fixturePath = Join-Path $temporaryRoot "gestor-eletrico-$migrationId.json"
$neonFixturePath = Join-Path (
    $temporaryRoot
) "gestor-eletrico-$migrationId-neon-fixture.json"
$localSnapshotPath = Join-Path $temporaryRoot "gestor-eletrico-$migrationId-local.json"
$neonSnapshotPath = Join-Path $temporaryRoot "gestor-eletrico-$migrationId-neon.json"
$temporaryPaths = @(
    $fixturePath,
    $neonFixturePath,
    $localSnapshotPath,
    $neonSnapshotPath
)

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

Push-Location $projectRoot
try {
    Remove-Item -LiteralPath "Env:DATABASE_URL" -ErrorAction SilentlyContinue

    Invoke-CheckedCommand `
        -Description "Verificando a integridade do SQLite" `
        -Executable $pythonExecutable `
        -Arguments @("manage.py", "check_sqlite_source")
    Invoke-CheckedCommand `
        -Description "Verificando migrations locais" `
        -Executable $pythonExecutable `
        -Arguments @("manage.py", "migrate", "--check")

    Invoke-CheckedCommand `
        -Description "Criando backup consistente do SQLite" `
        -Executable $pythonExecutable `
        -Arguments @(
            "manage.py",
            "backup_sqlite_source",
            "--output",
            $backupPath
        )
    Write-Host "Backup integro criado em: $backupPath" -ForegroundColor Green

    $backupUrlPath = $backupPath.Replace("\", "/")
    $env:DATABASE_URL = "sqlite:///$backupUrlPath"
    Invoke-CheckedCommand `
        -Description "Validando a copia imutavel do SQLite" `
        -Executable $pythonExecutable `
        -Arguments @("manage.py", "check_sqlite_source")
    Invoke-CheckedCommand `
        -Description "Gerando retrato dos dados locais" `
        -Executable $pythonExecutable `
        -Arguments @(
            "manage.py",
            "deployment_data_snapshot",
            "--output",
            $localSnapshotPath
        )

    Invoke-CheckedCommand `
        -Description "Exportando dados para arquivo temporario protegido" `
        -Executable $pythonExecutable `
        -Arguments @(
            "manage.py",
            "export_deployment_data",
            "--output",
            $fixturePath
        )

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
        )
    ) {
        throw "A conexao informada nao e uma URL PostgreSQL valida do Neon."
    }
    if ($parsedUrl.Host -match "-pooler") {
        throw (
            "Foi informada a URL agrupada (-pooler). Copie a URL direta " +
            "do Neon para a migracao."
        )
    }
    if ($parsedUrl.Query -notmatch "(^|[?&])sslmode=require(&|$)") {
        throw "A URL direta deve preservar o parametro sslmode=require."
    }

    $env:DATABASE_URL = $plainUrl
    $env:DJANGO_DATABASE_SSL_REQUIRE = "True"
    $env:DJANGO_DB_DISABLE_SERVER_SIDE_CURSORS = "False"
    $plainUrl = $null

    Invoke-CheckedCommand `
        -Description "Confirmando que o schema do Neon esta vazio" `
        -Executable $pythonExecutable `
        -Arguments @("manage.py", "assert_neon_pristine_database")
    Invoke-CheckedCommand `
        -Description "Criando o esquema no Neon" `
        -Executable $pythonExecutable `
        -Arguments @("manage.py", "migrate", "--noinput")
    Invoke-CheckedCommand `
        -Description "Confirmando que o Neon esta vazio" `
        -Executable $pythonExecutable `
        -Arguments @("manage.py", "assert_neon_import_target")
    Invoke-CheckedCommand `
        -Description "Importando os dados no Neon" `
        -Executable $pythonExecutable `
        -Arguments @("manage.py", "loaddata", $fixturePath)
    Invoke-CheckedCommand `
        -Description "Reexportando os dados recebidos pelo Neon" `
        -Executable $pythonExecutable `
        -Arguments @(
            "manage.py",
            "export_deployment_data",
            "--output",
            $neonFixturePath
        )
    Invoke-CheckedCommand `
        -Description "Gerando retrato dos dados no Neon" `
        -Executable $pythonExecutable `
        -Arguments @(
            "manage.py",
            "deployment_data_snapshot",
            "--output",
            $neonSnapshotPath
        )

    $sourceFixtureHash = (
        Get-FileHash -LiteralPath $fixturePath -Algorithm SHA256
    ).Hash
    $neonFixtureHash = (
        Get-FileHash -LiteralPath $neonFixturePath -Algorithm SHA256
    ).Hash
    $localSnapshotHash = (
        Get-FileHash -LiteralPath $localSnapshotPath -Algorithm SHA256
    ).Hash
    $neonSnapshotHash = (
        Get-FileHash -LiteralPath $neonSnapshotPath -Algorithm SHA256
    ).Hash
    if (
        $sourceFixtureHash -ne $neonFixtureHash -or
        $localSnapshotHash -ne $neonSnapshotHash
    ) {
        throw (
            "A validacao encontrou diferenca entre SQLite e Neon. " +
            "Nao conecte o Render a este banco."
        )
    }

    Invoke-CheckedCommand `
        -Description "Validando o administrador migrado" `
        -Executable $pythonExecutable `
        -Arguments @("manage.py", "ensure_network_admin", "--check")
    Invoke-CheckedCommand `
        -Description "Executando a verificacao final no Neon" `
        -Executable $pythonExecutable `
        -Arguments @("manage.py", "check")

    Write-Host ""
    Write-Host "Migracao concluida e validada." -ForegroundColor Green
    Write-Host "SQLite preservado em: $backupPath"
    Write-Host (
        "Agora use a URL agrupada (-pooler) em DATABASE_URL no Render e " +
        "esta URL direta em DIRECT_DATABASE_URL."
    )
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

    foreach ($temporaryPath in $temporaryPaths) {
        try {
            $resolvedTempRoot = [IO.Path]::GetFullPath($temporaryRoot)
            $resolvedTemporaryPath = [IO.Path]::GetFullPath($temporaryPath)
            if (
                $resolvedTemporaryPath.StartsWith(
                    $resolvedTempRoot,
                    [StringComparison]::OrdinalIgnoreCase
                ) -and
                (Test-Path -LiteralPath $resolvedTemporaryPath -PathType Leaf)
            ) {
                Remove-Item `
                    -LiteralPath $resolvedTemporaryPath `
                    -Force `
                    -ErrorAction Stop
            }
        }
        catch {
            Write-Warning (
                "Nao foi possivel apagar um arquivo temporario de migracao: " +
                $temporaryPath
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
