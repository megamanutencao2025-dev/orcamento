#Requires -Version 5.1
#Requires -RunAsAdministrator

<#
.SYNOPSIS
Gerencia as regras de firewall do Gestor Eletrico.

.DESCRIPTION
Mantem duas regras especificas e idempotentes: uma para a sub-rede local nos
perfis Privado/Dominio e outra restrita a faixa IPv4 do Tailscale. O padrao e
somente consultar o status; nenhuma regra e criada ou removida implicitamente.

.PARAMETER Action
Status consulta, Add cria ou corrige as regras e Remove remove somente essas regras.

.PARAMETER Port
Porta TCP das regras. Deve ser a mesma usada para iniciar o servidor.

.EXAMPLE
.\scripts\Manage-FirewallRule.ps1 -Action Status

.EXAMPLE
.\scripts\Manage-FirewallRule.ps1 -Action Add

.EXAMPLE
.\scripts\Manage-FirewallRule.ps1 -Action Remove
#>

[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Medium")]
param(
    [ValidateSet("Status", "Add", "Remove")]
    [string]$Action = "Status",

    [ValidateRange(1, 65535)]
    [int]$Port = 8010
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ruleDefinitions = @(
    [PSCustomObject]@{
        Name = "GestorEletrico-Waitress-LAN-TCP-$Port"
        DisplayName = "Gestor Eletrico - LAN - TCP $Port"
        Description = (
            "Permite acesso ao Gestor Eletrico via TCP/$Port somente a partir " +
            "da sub-rede local, nos perfis Privado e Dominio."
        )
        Profiles = @("Private", "Domain")
        RemoteAddresses = @("LocalSubnet")
    },
    [PSCustomObject]@{
        Name = "GestorEletrico-Waitress-Tailscale-TCP-$Port"
        DisplayName = "Gestor Eletrico - Tailscale - TCP $Port"
        Description = (
            "Permite acesso ao Gestor Eletrico via TCP/$Port somente a partir " +
            "da faixa IPv4 reservada ao Tailscale."
        )
        Profiles = @("Any")
        RemoteAddresses = @("100.64.0.0/10")
    }
)

function Get-ManagedFirewallRule {
    param([Parameter(Mandatory)][string]$Name)

    return Get-NetFirewallRule -Name $Name -ErrorAction SilentlyContinue
}

function Show-ManagedFirewallRule {
    param([Parameter(Mandatory)]$Rule)

    $portFilter = $Rule | Get-NetFirewallPortFilter
    $addressFilter = $Rule | Get-NetFirewallAddressFilter

    [PSCustomObject]@{
        Nome = $Rule.DisplayName
        Habilitada = $Rule.Enabled
        Direcao = $Rule.Direction
        Acao = $Rule.Action
        Perfis = "$($Rule.Profile)"
        Protocolo = $portFilter.Protocol
        PortaLocal = "$($portFilter.LocalPort)"
        OrigensPermitidas = "$($addressFilter.RemoteAddress -join ', ')"
    } | Format-List
}

switch ($Action) {
    "Status" {
        foreach ($definition in $ruleDefinitions) {
            $existingRule = Get-ManagedFirewallRule -Name $definition.Name
            if ($null -eq $existingRule) {
                Write-Host "A regra '$($definition.DisplayName)' nao esta configurada." `
                    -ForegroundColor Yellow
                continue
            }

            Show-ManagedFirewallRule -Rule $existingRule
        }
    }

    "Add" {
        foreach ($definition in $ruleDefinitions) {
            $existingRule = Get-ManagedFirewallRule -Name $definition.Name
            if ($null -eq $existingRule) {
                if ($PSCmdlet.ShouldProcess(
                        $definition.DisplayName,
                        "Criar regra de firewall restrita"
                    )) {
                    $createdRule = New-NetFirewallRule `
                        -Name $definition.Name `
                        -DisplayName $definition.DisplayName `
                        -Description $definition.Description `
                        -Enabled True `
                        -Direction Inbound `
                        -Action Allow `
                        -Profile $definition.Profiles `
                        -Protocol TCP `
                        -LocalPort $Port `
                        -RemoteAddress $definition.RemoteAddresses `
                        -EdgeTraversalPolicy Block
                    Write-Host "Regra '$($definition.DisplayName)' criada." `
                        -ForegroundColor Green
                    Show-ManagedFirewallRule -Rule $createdRule
                }
                continue
            }

            if ($PSCmdlet.ShouldProcess(
                    $definition.DisplayName,
                    "Reaplicar configuracao restrita"
                )) {
                $updatedRule = Set-NetFirewallRule `
                    -Name $definition.Name `
                    -NewDisplayName $definition.DisplayName `
                    -Description $definition.Description `
                    -Enabled True `
                    -Direction Inbound `
                    -Action Allow `
                    -Profile $definition.Profiles `
                    -Protocol TCP `
                    -LocalPort $Port `
                    -RemoteAddress $definition.RemoteAddresses `
                    -EdgeTraversalPolicy Block `
                    -PassThru
                Write-Host "Regra '$($definition.DisplayName)' validada." `
                    -ForegroundColor Green
                Show-ManagedFirewallRule -Rule $updatedRule
            }
        }
    }

    "Remove" {
        foreach ($definition in $ruleDefinitions) {
            $existingRule = Get-ManagedFirewallRule -Name $definition.Name
            if ($null -eq $existingRule) {
                Write-Host "A regra '$($definition.DisplayName)' ja nao existe." `
                    -ForegroundColor Yellow
                continue
            }

            if ($PSCmdlet.ShouldProcess(
                    $definition.DisplayName,
                    "Remover regra de firewall"
                )) {
                Remove-NetFirewallRule -Name $definition.Name
                Write-Host "Regra '$($definition.DisplayName)' removida." `
                    -ForegroundColor Green
            }
        }
    }
}
