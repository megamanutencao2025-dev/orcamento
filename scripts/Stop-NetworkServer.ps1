#Requires -Version 5.1

<#
.SYNOPSIS
Encerra somente os processos do servidor de rede deste projeto.

.EXAMPLE
.\scripts\Stop-NetworkServer.ps1
#>

[CmdletBinding(SupportsShouldProcess)]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$escapedProjectRoot = [Regex]::Escape($projectRoot)
$targets = @(
    Get-CimInstance Win32_Process |
        Where-Object {
            -not [string]::IsNullOrWhiteSpace($_.CommandLine) -and
            $_.CommandLine -match $escapedProjectRoot -and
            (
                $_.CommandLine -match (
                    "waitress.+eletrico\.wsgi:application"
                ) -or
                $_.CommandLine -match (
                    "Start-NetworkServer\.ps1"
                )
            )
        }
)

if ($targets.Count -eq 0) {
    Write-Host "Nenhum servidor de rede deste projeto esta ativo."
    return
}

# Encerra os processos Python antes do PowerShell supervisor.
$orderedTargets = @(
    $targets |
        Sort-Object @{
            Expression = {
                if ($_.Name -like "python*") {
                    return 0
                }
                return 1
            }
        }
)
foreach ($target in $orderedTargets) {
    $description = "$($target.Name) PID $($target.ProcessId)"
    if ($PSCmdlet.ShouldProcess($description, "Encerrar")) {
        Stop-Process `
            -Id $target.ProcessId `
            -Force `
            -ErrorAction SilentlyContinue
    }
}

if ($WhatIfPreference) {
    Write-Host "Simulacao concluida; nenhum processo foi encerrado."
}
else {
    Write-Host "Servidor de rede encerrado." -ForegroundColor Green
}
