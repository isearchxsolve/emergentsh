[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 20130,

    [ValidateRange(1, 10)]
    [int]$MinimumHealthyProviders = 2,

    [ValidateRange(30, 1800)]
    [int]$ProbeTimeoutSeconds = 600,

    [switch]$ProbeOnly,
    [switch]$RestartGateway,
    [switch]$SkipBackup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$omniHome = Join-Path $env:USERPROFILE ".omniroute"
$envFile = Join-Path $omniHome ".env"
$databaseFile = Join-Path $omniHome "storage.sqlite"
$omniCli = Join-Path $env:USERPROFILE "node_modules\omniroute\bin\omniroute.mjs"
$baseUrl = "http://127.0.0.1:$Port"
$providersUrl = "$baseUrl/dashboard/providers"

# Direct probes cover the connections that NeonBuild's current composite
# policies may use. Missing providers are reported, not silently ignored.
$directModels = @(
    "nvidia/nvidia/nemotron-3-super-120b-a12b",
    "groq/llama-3.3-70b-versatile",
    "kimi-coding/kimi-coding-default",
    "mistral/codestral-2508",
    "codex/gpt-5.6-sol",
    "gemini/gemini-2.5-pro"
)
$compositeModels = @(
    "auto/best-reasoning",
    "auto/best-coding"
)

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Get-EnvValue {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Name
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    foreach ($line in Get-Content -LiteralPath $Path) {
        # PowerShell's \s does not consume a UTF-8 BOM when it appears on the
        # first line, so normalize it before matching dotenv entries.
        $normalizedLine = $line.TrimStart([char]0xFEFF)
        if ($normalizedLine -match "^\s*(?:export\s+)?$([regex]::Escape($Name))\s*=\s*(.*?)\s*$") {
            $value = $Matches[1].Trim()
            if (
                $value.Length -ge 2 -and
                (($value.StartsWith('"') -and $value.EndsWith('"')) -or
                 ($value.StartsWith("'") -and $value.EndsWith("'")))
            ) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }
    return $null
}

function Import-OmniRouteEnvironment {
    if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
        throw "OmniRoute environment file was not found at $envFile"
    }

    $storageKey = Get-EnvValue -Path $envFile -Name "STORAGE_ENCRYPTION_KEY"
    if ([string]::IsNullOrWhiteSpace($storageKey)) {
        throw "STORAGE_ENCRYPTION_KEY is missing from $envFile. Refusing to start against encrypted credentials."
    }

    # Explicitly set the storage contract. Relying on a wrapper's inherited
    # environment was the root cause of the previous missing-key runtime.
    $env:STORAGE_ENCRYPTION_KEY = $storageKey
    $env:STORAGE_ENCRYPTION_KEY_VERSION = (Get-EnvValue -Path $envFile -Name "STORAGE_ENCRYPTION_KEY_VERSION")
    if ([string]::IsNullOrWhiteSpace($env:STORAGE_ENCRYPTION_KEY_VERSION)) {
        $env:STORAGE_ENCRYPTION_KEY_VERSION = "v1"
    }
    $env:DATA_DIR = $omniHome
    $env:OMNIROUTE_PORT = "$Port"
    $env:PORT = "$Port"
    $env:DASHBOARD_PORT = "$Port"
    $env:API_PORT = "$Port"
    $env:OMNIROUTE_BASE_URL = "$baseUrl/v1"

    foreach ($name in @(
        "OMNIROUTE_DISABLE_CREDENTIAL_HEALTH_CHECK",
        "OMNIROUTE_DISABLE_TOKEN_HEALTHCHECK",
        "PLAYWRIGHT_BROWSERS_PATH",
        "WEB_COOKIE_USE_BROWSER",
        "OMNIROUTE_BROWSER_POOL"
    )) {
        $value = Get-EnvValue -Path $envFile -Name $name
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            Set-Item -Path "Env:$name" -Value $value
        }
    }
}

function Test-GatewayListener {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    return $null -ne $listener
}

function Find-SupportedNode {
    $candidates = [System.Collections.Generic.List[string]]::new()
    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeCommand) {
        $candidates.Add($nodeCommand.Source)
    }

    $codexRuntimeRoot = Join-Path $env:LOCALAPPDATA "OpenAI\Codex\runtimes\cua_node"
    if (Test-Path -LiteralPath $codexRuntimeRoot -PathType Container) {
        Get-ChildItem -LiteralPath $codexRuntimeRoot -Directory -ErrorAction SilentlyContinue |
            ForEach-Object {
                $candidate = Join-Path $_.FullName "bin\node.exe"
                if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                    $candidates.Add($candidate)
                }
            }
    }

    foreach ($candidate in $candidates | Select-Object -Unique) {
        try {
            $versionText = (& $candidate --version 2>$null).TrimStart('v')
            $major = [int]($versionText.Split('.')[0])
            if ($major -eq 20 -or $major -eq 22 -or $major -eq 24) {
                return $candidate
            }
        } catch {
            continue
        }
    }
    throw "No OmniRoute-compatible Node.js runtime was found (supported majors: 20, 22, 24)."
}

function Restart-OmniRoute {
    if (-not (Test-Path -LiteralPath $omniCli -PathType Leaf)) {
        throw "OmniRoute CLI was not found at $omniCli"
    }

    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($listener) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        $isOmniRoute = $process.Name -eq "node.exe" -and (
            $process.CommandLine -match "omniroute" -or
            $process.CommandLine -match "server-ws\.mjs"
        )
        if (-not $isOmniRoute) {
            throw "Port $Port belongs to an unexpected process. Refusing to stop PID $($listener.OwningProcess)."
        }
        Stop-Process -Id $listener.OwningProcess -ErrorAction Stop
        $deadline = (Get-Date).AddSeconds(20)
        while ((Test-GatewayListener) -and (Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 250
        }
        if (Test-GatewayListener) {
            throw "Verified OmniRoute PID $($listener.OwningProcess) did not release port $Port."
        }
    }

    $nodePath = Find-SupportedNode
    # server-ws.mjs spawns `node` by name; put the selected compatible runtime
    # first so the child cannot silently resolve a different Node major.
    $env:PATH = "$(Split-Path -Parent $nodePath);$env:PATH"
    $startArguments = @{
        FilePath = $nodePath
        ArgumentList = @("`"$omniCli`"", "--port", "$Port", "--no-open")
        WindowStyle = "Hidden"
    }
    Start-Process @startArguments | Out-Null

    $deadline = (Get-Date).AddSeconds(90)
    while (-not (Test-GatewayListener) -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
    }
    if (-not (Test-GatewayListener)) {
        throw "OmniRoute did not start on port $Port within 90 seconds."
    }
}

function Invoke-RouteProbe {
    param(
        [Parameter(Mandatory)] [string]$Model,
        [Parameter(Mandatory)] [string]$ApiKey
    )

    $headers = @{
        Authorization = "Bearer $ApiKey"
        Accept = "application/json"
    }
    $body = @{
        model = $Model
        messages = @(@{
            role = "user"
            content = "Reply with exactly: healthy"
        })
        temperature = 0
        max_tokens = 12
        stream = $false
    } | ConvertTo-Json -Depth 6 -Compress

    $started = Get-Date
    try {
        $requestArguments = @{
            Uri = "$baseUrl/v1/chat/completions"
            Method = "Post"
            Headers = $headers
            ContentType = "application/json"
            Body = $body
            TimeoutSec = $ProbeTimeoutSeconds
        }
        $response = Invoke-RestMethod @requestArguments
        $content = $response.choices[0].message.content
        $healthy = -not [string]::IsNullOrWhiteSpace([string]$content)
        return [pscustomobject]@{
            Model = $Model
            Healthy = $healthy
            Status = if ($healthy) { "200 / content" } else { "200 / empty" }
            Seconds = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
        }
    } catch {
        $statusCode = $null
        $responseProperty = $_.Exception.PSObject.Properties["Response"]
        if ($responseProperty -and $responseProperty.Value -and $responseProperty.Value.StatusCode) {
            $statusCode = [int]$responseProperty.Value.StatusCode
        }
        return [pscustomobject]@{
            Model = $Model
            Healthy = $false
            Status = if ($statusCode) { "HTTP $statusCode" } else { $_.Exception.GetType().Name }
            Seconds = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
        }
    }
}

if (-not (Test-Path -LiteralPath $omniHome -PathType Container)) {
    throw "OmniRoute data directory was not found at $omniHome"
}

Import-OmniRouteEnvironment

if (-not $ProbeOnly -and -not $SkipBackup) {
    Write-Step "Creating a recoverable OmniRoute configuration backup"
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupDirectory = Join-Path $omniHome "reauth-backups\$timestamp"
    New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null
    foreach ($source in @($envFile, $databaseFile)) {
        if (Test-Path -LiteralPath $source -PathType Leaf) {
            Copy-Item -LiteralPath $source -Destination $backupDirectory
        }
    }
    Write-Host "Backup: $backupDirectory"
}

if ($RestartGateway) {
    Write-Step "Restarting only the verified OmniRoute process on port $Port"
    Restart-OmniRoute
} elseif (-not (Test-GatewayListener)) {
    Write-Step "OmniRoute is not listening; starting it on port $Port"
    Restart-OmniRoute
}

if (-not $ProbeOnly) {
    Write-Step "Opening the authenticated OmniRoute Providers page"
    Write-Host "In the dashboard, complete these actions:"
    Write-Host "  1. Sign in to the OmniRoute dashboard."
    Write-Host "  2. Reconnect OAuth providers (Codex, Gemini CLI, Kimi Coding, GitHub/Claude if used)."
    Write-Host "  3. Replace and test rejected API keys (NVIDIA NIM, Groq, Mistral/OpenRouter)."
    Write-Host "  4. Disable stale duplicate connections that still return 401/403."
    Write-Host "  5. In Combos, keep at least two healthy providers in auto/best-reasoning and auto/best-coding."
    Write-Host ""
    Write-Host "This script deliberately does NOT call reset-encrypted-columns; that command erases provider credentials."
    Start-Process $providersUrl | Out-Null
    Read-Host "Press Enter only after the dashboard connection tests are green" | Out-Null
}

$apiKey = Get-EnvValue -Path $envFile -Name "OMNIROUTE_API_KEY"
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    $apiKey = $env:OMNIROUTE_API_KEY
}
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw "OMNIROUTE_API_KEY is missing from $envFile. Create/copy an endpoint key in Dashboard -> Endpoints."
}

Write-Step "Running real short completions against each provider connection"
$directResults = @($directModels | ForEach-Object { Invoke-RouteProbe -Model $_ -ApiKey $apiKey })
$directResults | Format-Table Model, Healthy, Status, Seconds -AutoSize

Write-Step "Validating the two composite routes used by NeonBuild"
$compositeResults = @($compositeModels | ForEach-Object { Invoke-RouteProbe -Model $_ -ApiKey $apiKey })
$compositeResults | Format-Table Model, Healthy, Status, Seconds -AutoSize

$healthyProviderCount = @($directResults | Where-Object Healthy).Count
$failedComposites = @($compositeResults | Where-Object { -not $_.Healthy })
$ready = $healthyProviderCount -ge $MinimumHealthyProviders -and $failedComposites.Count -eq 0

Write-Step "Readiness result"
Write-Host "Healthy direct providers: $healthyProviderCount (required: $MinimumHealthyProviders)"
Write-Host "Healthy NeonBuild composite routes: $($compositeResults.Count - $failedComposites.Count)/$($compositeResults.Count)"

if (-not $ready) {
    Write-Host "OmniRoute re-authentication is incomplete. Return to $providersUrl and repair the failed rows above." -ForegroundColor Red
    exit 2
}

Write-Host "OmniRoute is ready for strict-live NeonBuild generation." -ForegroundColor Green
exit 0
