#Requires -Version 5.1

<#
.SYNOPSIS
Prepara e inicia o Gestor Eletrico para acesso pela rede local e pelo Tailscale.

.DESCRIPTION
Detecta enderecos IPv4, configura variaveis Django somente para o processo atual,
aplica migracoes, verifica o projeto, coleta arquivos estaticos e inicia o Waitress.
Nao cria nem altera regras de firewall.

.PARAMETER Port
Porta TCP do servidor. O padrao e 8010.

.PARAMETER BindAddress
Endereco IPv4 usado pelo Waitress. O padrao 0.0.0.0 aceita as interfaces locais.

.PARAMETER PythonPath
Caminho opcional para python.exe. Na ausencia, prioriza .venv\Scripts\python.exe.

.PARAMETER PreflightOnly
Executa toda a preparacao e mostra as URLs sem iniciar o Waitress.

.EXAMPLE
.\scripts\Start-NetworkServer.ps1

.EXAMPLE
.\scripts\Start-NetworkServer.ps1 -PreflightOnly

.EXAMPLE
.\scripts\Start-NetworkServer.ps1 -Port 8011
#>

[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8010,

    [ValidateNotNullOrEmpty()]
    [string]$BindAddress = "0.0.0.0",

    [string]$PythonPath,

    [switch]$PreflightOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-IPv4Address {
    param([Parameter(Mandatory)][string]$Address)

    $parsedAddress = $null
    return (
        [System.Net.IPAddress]::TryParse($Address, [ref]$parsedAddress) -and
        $parsedAddress.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork
    )
}

function Test-PrivateLanIPv4 {
    param([Parameter(Mandatory)][string]$Address)

    if (-not (Test-IPv4Address -Address $Address)) {
        return $false
    }

    $octets = ([System.Net.IPAddress]::Parse($Address)).GetAddressBytes()
    return (
        $octets[0] -eq 10 -or
        ($octets[0] -eq 172 -and $octets[1] -ge 16 -and $octets[1] -le 31) -or
        ($octets[0] -eq 192 -and $octets[1] -eq 168)
    )
}

function Get-NetworkIPv4EntriesFromDotNet {
    $entries = @()
    $interfaces = [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces()

    foreach ($networkInterface in $interfaces) {
        if (
            $networkInterface.OperationalStatus -ne
            [System.Net.NetworkInformation.OperationalStatus]::Up
        ) {
            continue
        }

        foreach ($unicastAddress in $networkInterface.GetIPProperties().UnicastAddresses) {
            if (
                $unicastAddress.Address.AddressFamily -ne
                [System.Net.Sockets.AddressFamily]::InterNetwork
            ) {
                continue
            }

            $entries += [PSCustomObject]@{
                IPAddress = $unicastAddress.Address.ToString()
                InterfaceAlias = $networkInterface.Name
                AddressState = "Preferred"
                SkipAsSource = $false
            }
        }
    }

    return @($entries)
}

function Get-NetworkIPv4Entries {
    param([ValidateRange(1, 30)][int]$TimeoutSeconds = 5)

    if ($null -eq (Get-Command "Get-NetIPAddress" -ErrorAction SilentlyContinue)) {
        return @(Get-NetworkIPv4EntriesFromDotNet)
    }

    $discoveryJob = $null
    try {
        $discoveryJob = Start-Job -ScriptBlock {
            Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
                Where-Object {
                    $_.AddressState -eq "Preferred" -and
                    -not $_.SkipAsSource
                } |
                Select-Object IPAddress, InterfaceAlias
        }
        $completedJob = Wait-Job -Job $discoveryJob -Timeout $TimeoutSeconds
        if ($null -eq $completedJob) {
            Stop-Job -Job $discoveryJob -ErrorAction SilentlyContinue
            Write-Warning (
                "A descoberta com Get-NetIPAddress excedeu $TimeoutSeconds segundos; " +
                "usando a leitura local alternativa."
            )
            return @(Get-NetworkIPv4EntriesFromDotNet)
        }

        $entries = @(Receive-Job -Job $discoveryJob -ErrorAction SilentlyContinue)
        if ($entries.Count -eq 0) {
            return @(Get-NetworkIPv4EntriesFromDotNet)
        }

        return @($entries)
    }
    finally {
        if ($null -ne $discoveryJob) {
            Remove-Job -Job $discoveryJob -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-TailscaleIPv4 {
    param([object[]]$Entries)

    $addresses = @(
        $Entries |
            Where-Object {
                $_.InterfaceAlias -like "*Tailscale*" -and
                (Test-IPv4Address -Address $_.IPAddress)
            } |
            ForEach-Object { $_.IPAddress } |
            Sort-Object -Unique
    )
    return @($addresses)
}

function Get-LanIPv4 {
    param([object[]]$Entries)

    $ignoredInterfaces = (
        "Loopback|Tailscale|vEthernet|VirtualBox|VMware|WSL|Docker|Hyper-V"
    )
    $addresses = @(
        $Entries |
            Where-Object {
                $_.InterfaceAlias -notmatch $ignoredInterfaces -and
                (Test-PrivateLanIPv4 -Address $_.IPAddress)
            } |
            ForEach-Object { $_.IPAddress } |
            Sort-Object -Unique
    )
    return @($addresses)
}

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

        throw "Python nao encontrado no caminho informado: $RequestedPath"
    }

    $virtualEnvironmentPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $virtualEnvironmentPython -PathType Leaf) {
        return $virtualEnvironmentPython
    }

    $systemPython = Get-Command "python" -ErrorAction SilentlyContinue
    if ($null -ne $systemPython) {
        return $systemPython.Source
    }

    throw "Python nao encontrado. Crie o ambiente .venv ou informe -PythonPath."
}

function Get-OrCreateNetworkSecret {
    param([Parameter(Mandatory)][string]$ProjectRoot)

    $databaseDirectory = Join-Path $ProjectRoot "database"
    $secretPath = Join-Path $databaseDirectory ".network-secret"
    [System.IO.Directory]::CreateDirectory($databaseDirectory) | Out-Null

    if (Test-Path -LiteralPath $secretPath -PathType Leaf) {
        $storedSecret = [System.IO.File]::ReadAllText($secretPath).Trim()
        if ($storedSecret.Length -lt 32) {
            throw "A chave em database\.network-secret e invalida. Corrija ou remova o arquivo manualmente."
        }
        return $storedSecret
    }

    [byte[]]$randomBytes = New-Object byte[] 48
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($randomBytes)
    }
    finally {
        $generator.Dispose()
    }

    $newSecret = [Convert]::ToBase64String($randomBytes)
    [System.IO.File]::WriteAllText(
        $secretPath,
        $newSecret,
        (New-Object System.Text.UTF8Encoding($false))
    )
    return $newSecret
}

function Assert-PortAvailable {
    param(
        [Parameter(Mandatory)][int]$RequestedPort,
        [Parameter(Mandatory)][string]$RequestedAddress
    )

    $address = [System.Net.IPAddress]::Parse($RequestedAddress)
    $probe = [System.Net.Sockets.TcpListener]::new($address, $RequestedPort)
    $probe.Server.ExclusiveAddressUse = $true
    try {
        $probe.Start()
    }
    catch {
        throw (
            "A porta $RequestedPort nao esta disponivel em $RequestedAddress. " +
            "Nenhum processo foi encerrado. Escolha outra porta com -Port."
        )
    }
    finally {
        $probe.Stop()
    }
}

function Invoke-DjangoCommand {
    param(
        [Parameter(Mandatory)][string]$PythonExecutable,
        [Parameter(Mandatory)][string]$Description,
        [Parameter(Mandatory)][string[]]$Arguments
    )

    Write-Host "$Description..." -ForegroundColor Cyan
    & $PythonExecutable @Arguments
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

function Assert-NeonConnectionPair {
    param(
        [Parameter(Mandatory)][string]$RuntimeUrl,
        [Parameter(Mandatory)][string]$DirectUrl
    )

    $runtimeUri = $null
    $directUri = $null
    if (
        -not [Uri]::TryCreate(
            $RuntimeUrl,
            [UriKind]::Absolute,
            [ref]$runtimeUri
        ) -or
        -not [Uri]::TryCreate(
            $DirectUrl,
            [UriKind]::Absolute,
            [ref]$directUri
        )
    ) {
        throw "As URLs PostgreSQL informadas nao sao validas."
    }

    if (
        $runtimeUri.Scheme -notin @("postgres", "postgresql") -or
        $directUri.Scheme -notin @("postgres", "postgresql") -or
        -not $runtimeUri.Host.EndsWith(
            ".neon.tech",
            [StringComparison]::OrdinalIgnoreCase
        ) -or
        -not $directUri.Host.EndsWith(
            ".neon.tech",
            [StringComparison]::OrdinalIgnoreCase
        )
    ) {
        throw "DATABASE_URL e DIRECT_DATABASE_URL devem pertencer ao Neon."
    }
    if (
        $runtimeUri.Host -notmatch "-pooler" -or
        $directUri.Host -match "-pooler"
    ) {
        throw (
            "DATABASE_URL deve usar -pooler e DIRECT_DATABASE_URL deve " +
            "usar a conexao direta."
        )
    }

    $expectedDirectHost = $runtimeUri.Host -replace "-pooler(?=\.)", ""
    $runtimeDatabase = [Uri]::UnescapeDataString(
        $runtimeUri.AbsolutePath.Trim("/")
    )
    $directDatabase = [Uri]::UnescapeDataString(
        $directUri.AbsolutePath.Trim("/")
    )
    $runtimeUsername = (
        [Uri]::UnescapeDataString($runtimeUri.UserInfo) -split ":", 2
    )[0]
    $directUsername = (
        [Uri]::UnescapeDataString($directUri.UserInfo) -split ":", 2
    )[0]
    if (
        -not $expectedDirectHost.Equals(
            $directUri.Host,
            [StringComparison]::OrdinalIgnoreCase
        ) -or
        $runtimeDatabase -ne $directDatabase -or
        $runtimeUsername -ne $directUsername
    ) {
        throw (
            "As URLs agrupada e direta nao apontam para o mesmo " +
            "endpoint, banco e usuario do Neon."
        )
    }
    if (
        $runtimeUri.Query -notmatch "(^|[?&])sslmode=require(&|$)" -or
        $directUri.Query -notmatch "(^|[?&])sslmode=require(&|$)"
    ) {
        throw "As duas URLs devem preservar o parametro sslmode=require."
    }
}

if (-not (Test-IPv4Address -Address $BindAddress)) {
    throw "BindAddress deve ser um endereco IPv4 valido."
}

$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$managePath = Join-Path $projectRoot "manage.py"
if (-not (Test-Path -LiteralPath $managePath -PathType Leaf)) {
    throw "manage.py nao encontrado em $projectRoot."
}

Assert-PortAvailable -RequestedPort $Port -RequestedAddress $BindAddress

$pythonExecutable = Resolve-PythonExecutable `
    -ProjectRoot $projectRoot `
    -RequestedPath $PythonPath
$networkEntries = @(Get-NetworkIPv4Entries)
$lanAddresses = @(Get-LanIPv4 -Entries $networkEntries)
$tailscaleAddresses = @(Get-TailscaleIPv4 -Entries $networkEntries)
$explicitBindAddresses = @()
if ($BindAddress -ne "0.0.0.0") {
    $explicitBindAddresses = @($BindAddress)
}
$allowedHosts = @(
    @("127.0.0.1", "localhost") +
    $explicitBindAddresses +
    $lanAddresses +
    $tailscaleAddresses |
        Sort-Object -Unique
)
$trustedOrigins = @(
    $allowedHosts |
        ForEach-Object { "http://${_}:$Port" } |
        Sort-Object -Unique
)

$managedEnvironmentNames = @(
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DJANGO_DEBUG",
    "DJANGO_REQUIRE_LOGIN",
    "DJANGO_HTTPS_MODE",
    "DJANGO_SECRET_KEY",
    "DATABASE_URL"
)
$previousEnvironment = @{}
foreach ($environmentName in $managedEnvironmentNames) {
    $previousEnvironment[$environmentName] = (
        [Environment]::GetEnvironmentVariable(
            $environmentName,
            "Process"
        )
    )
}

try {
    $env:DJANGO_ALLOWED_HOSTS = $allowedHosts -join ","
    $env:DJANGO_CSRF_TRUSTED_ORIGINS = $trustedOrigins -join ","
    $env:DJANGO_DEBUG = "False"
    $env:DJANGO_REQUIRE_LOGIN = "True"
    $env:DJANGO_HTTPS_MODE = "False"
    $env:DJANGO_SECRET_KEY = Get-OrCreateNetworkSecret `
        -ProjectRoot $projectRoot

    $runtimeDatabaseUrl = [Environment]::GetEnvironmentVariable(
        "DATABASE_URL",
        "Process"
    )
    if ($null -ne $runtimeDatabaseUrl) {
        $runtimeDatabaseUrl = $runtimeDatabaseUrl.Trim()
    }
    $directDatabaseUrl = [Environment]::GetEnvironmentVariable(
        "DIRECT_DATABASE_URL",
        "Process"
    )
    if ($null -ne $directDatabaseUrl) {
        $directDatabaseUrl = $directDatabaseUrl.Trim()
    }
    $usesPostgresql = (
        -not [string]::IsNullOrWhiteSpace($runtimeDatabaseUrl) -and
        $runtimeDatabaseUrl -match "^postgres(ql)?://"
    )
    if (
        $usesPostgresql -and
        [string]::IsNullOrWhiteSpace($directDatabaseUrl)
    ) {
        throw (
            "DATABASE_URL aponta para PostgreSQL. Defina tambem " +
            "DIRECT_DATABASE_URL para aplicar migrations sem o pool."
        )
    }
    if ($usesPostgresql) {
        Assert-NeonConnectionPair `
            -RuntimeUrl $runtimeDatabaseUrl `
            -DirectUrl $directDatabaseUrl
    }

    Push-Location $projectRoot
    try {
        & $pythonExecutable "-c" "import waitress"
        if ($LASTEXITCODE -ne 0) {
            throw "Waitress nao esta instalado no ambiente Python selecionado."
        }

        if ($usesPostgresql) {
            Invoke-DjangoCommand `
                -PythonExecutable $pythonExecutable `
                -Description "Validando as conexoes agrupada e direta" `
                -Arguments @(
                    "manage.py",
                    "validate_neon_connection_pair"
                )
        }

        if ($usesPostgresql) {
            $env:DATABASE_URL = $directDatabaseUrl
        }
        try {
            Invoke-DjangoCommand `
                -PythonExecutable $pythonExecutable `
                -Description "Aplicando migracoes" `
                -Arguments @("manage.py", "migrate", "--noinput")
        }
        finally {
            if ($usesPostgresql) {
                $env:DATABASE_URL = $runtimeDatabaseUrl
            }
        }
        Invoke-DjangoCommand `
            -PythonExecutable $pythonExecutable `
            -Description "Verificando a aplicacao" `
            -Arguments @("manage.py", "check")

        if ($PreflightOnly) {
            Write-Host "Verificando credencial administrativa..." `
                -ForegroundColor Cyan
            & $pythonExecutable `
                "manage.py" `
                "ensure_network_admin" `
                "--check" `
                2>$null
            if ($LASTEXITCODE -ne 0) {
                Write-Warning (
                    "Nenhum superusuario ativo foi confirmado. Execute " +
                    "este script sem -PreflightOnly para cadastrar a " +
                    "credencial antes de iniciar o servidor."
                )
            }
        }
        else {
            Invoke-DjangoCommand `
                -PythonExecutable $pythonExecutable `
                -Description "Garantindo credencial administrativa" `
                -Arguments @("manage.py", "ensure_network_admin")
        }

        Invoke-DjangoCommand `
            -PythonExecutable $pythonExecutable `
            -Description "Coletando arquivos estaticos" `
            -Arguments @("manage.py", "collectstatic", "--noinput")

        Write-Host ""
        Write-Host "Aplicacao pronta para acesso:" -ForegroundColor Green
        Write-Host "  Local:     http://127.0.0.1:$Port"
        foreach ($address in $lanAddresses) {
            Write-Host "  Rede LAN:  http://${address}:$Port"
        }
        foreach ($address in $tailscaleAddresses) {
            Write-Host "  Tailscale: http://${address}:$Port"
        }
        if ($lanAddresses.Count -eq 0) {
            Write-Warning "Nenhum IPv4 de rede local foi detectado."
        }
        if ($tailscaleAddresses.Count -eq 0) {
            Write-Warning "Nenhum IPv4 do Tailscale foi detectado."
        }

        if ($PreflightOnly) {
            Write-Host ""
            Write-Host (
                "Pre-verificacao concluida; o servidor nao foi iniciado."
            ) -ForegroundColor Green
            return
        }

        Write-Host ""
        Write-Host (
            "Iniciando Waitress em ${BindAddress}:$Port. " +
            "Use Ctrl+C para encerrar."
        ) -ForegroundColor Green
        & $pythonExecutable `
            "-m" `
            "waitress" `
            "--listen=${BindAddress}:$Port" `
            "eletrico.wsgi:application"
        if ($LASTEXITCODE -ne 0) {
            throw "O servidor Waitress foi encerrado com codigo $LASTEXITCODE."
        }
    }
    finally {
        if ($usesPostgresql) {
            $env:DATABASE_URL = $runtimeDatabaseUrl
        }
        Pop-Location
    }
}
finally {
    foreach ($environmentName in $managedEnvironmentNames) {
        try {
            Restore-ProcessEnvironment `
                -Name $environmentName `
                -PreviousValue $previousEnvironment[$environmentName]
        }
        catch {
            Write-Warning (
                "Falha ao restaurar a variavel $environmentName. " +
                "Feche este PowerShell antes de continuar."
            )
        }
    }
}
