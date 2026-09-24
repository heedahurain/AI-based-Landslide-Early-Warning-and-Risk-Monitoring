<#
.SYNOPSIS
  Windows mirror of the Makefile.

.DESCRIPTION
  GNU make is not installed on a default Windows setup, and this project is
  built on Windows. Every target here matches the Makefile target of the same
  name, so documentation can refer to `make <target>` without stranding a
  Windows developer.

.EXAMPLE
  ./make.ps1 up
  ./make.ps1 test
  ./make.ps1 probe-sources
#>

param(
    [Parameter(Position = 0)]
    [string]$Target = "help",

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Compose = @("compose", "-f", (Join-Path $RepoRoot "infra/docker-compose.yml"))
$VenvPy = Join-Path $RepoRoot ".venv/Scripts/python.exe"

function Invoke-Compose {
    param([string[]]$ComposeArgs)
    & docker @($Compose + $ComposeArgs)
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Invoke-Checked {
    param([string]$Exe, [string[]]$ExeArgs, [string]$WorkDir = $RepoRoot)
    Push-Location $WorkDir
    try {
        & $Exe @ExeArgs
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    finally { Pop-Location }
}

switch ($Target) {
    "help" {
        Write-Host ""
        Write-Host "  ShailSuraksha targets" -ForegroundColor Cyan
        Write-Host ""
        @(
            @("up", "Start the core stack"),
            @("up-workers", "Start the stack including Celery worker and beat"),
            @("up-ml", "Start the stack including MLflow"),
            @("down", "Stop everything"),
            @("clean", "Stop everything and delete volumes"),
            @("logs", "Follow logs"),
            @("ps", "Show service status"),
            @("migrate", "Apply Alembic migrations"),
            @("test", "Run every test suite"),
            @("test-api", "Run the Python test suites"),
            @("test-web", "Run web tests and the contrast audit"),
            @("lint", "Lint Python and TypeScript"),
            @("format", "Format Python and TypeScript"),
            @("typecheck", "Type-check Python and TypeScript"),
            @("contrast", "Audit design tokens against WCAG AA"),
            @("probe-sources", "Re-probe upstream data sources"),
            @("install-py", "Create the venv and install dev dependencies"),
            @("install-web", "Install web dependencies")
        ) | ForEach-Object { "{0,-16} {1}" -f $_[0], $_[1] } | Write-Host
        Write-Host ""
    }

    "up" {
        Invoke-Compose @("up", "-d", "--build")
        Write-Host ""
        Write-Host "  API      http://localhost:8000/docs"
        Write-Host "  Web      http://localhost:3000"
        Write-Host "  MinIO    http://localhost:9002"
        Write-Host ""
    }
    "up-workers" { Invoke-Compose @("--profile", "workers", "up", "-d", "--build") }
    "up-ml" { Invoke-Compose @("--profile", "ml", "up", "-d", "--build") }
    "down" { Invoke-Compose @("down") }
    "clean" { Invoke-Compose @("down", "-v") }
    "logs" { Invoke-Compose @("logs", "-f") }
    "ps" { Invoke-Compose @("ps") }
    "restart" { Invoke-Compose @("restart", "api", "worker") }
    "build" { Invoke-Compose @("build") }

    "migrate" { Invoke-Compose @("exec", "api", "alembic", "upgrade", "head") }
    "revision" {
        if (-not $Rest) { throw "Usage: ./make.ps1 revision 'add slope units'" }
        Invoke-Compose @("exec", "api", "alembic", "revision", "--autogenerate", "-m", ($Rest -join " "))
    }
    "seed" { Invoke-Compose @("exec", "api", "python", "-m", "app.db.seed") }
    "train" { Invoke-Compose @("--profile", "ml", "exec", "api", "python", "-m", "ml.train") }

    "test" {
        $env:PYTHONPATH = "api"
        Invoke-Checked $VenvPy @("-m", "pytest", "-q")
        Invoke-Checked "npm" @("run", "test") (Join-Path $RepoRoot "web")
    }
    "test-api" {
        $env:PYTHONPATH = "api"
        Invoke-Checked $VenvPy @("-m", "pytest", "-q")
    }
    "test-web" { Invoke-Checked "npm" @("run", "test") (Join-Path $RepoRoot "web") }

    "lint" {
        Invoke-Checked $VenvPy @("-m", "ruff", "check", "api", "ingest", "ml")
        Invoke-Checked "npm" @("run", "lint") (Join-Path $RepoRoot "web")
    }
    "format" {
        Invoke-Checked $VenvPy @("-m", "ruff", "format", "api", "ingest", "ml")
        Invoke-Checked "npm" @("run", "format") (Join-Path $RepoRoot "web")
    }
    "typecheck" {
        Invoke-Checked $VenvPy @("-m", "mypy", "api", "ingest", "ml")
        Invoke-Checked "npm" @("run", "typecheck") (Join-Path $RepoRoot "web")
    }
    "contrast" { Invoke-Checked "npm" @("run", "contrast") (Join-Path $RepoRoot "web") }

    "probe-sources" { Invoke-Checked "python" @("scripts/probe_sources.py") }

    "install-py" {
        Invoke-Checked "python" @("-m", "venv", ".venv")
        Invoke-Checked $VenvPy @("-m", "pip", "install", "--upgrade", "pip")
        Invoke-Checked $VenvPy @("-m", "pip", "install", "-r", "requirements-dev.txt")
    }
    "install-web" { Invoke-Checked "npm" @("ci") (Join-Path $RepoRoot "web") }

    default {
        Write-Error "Unknown target '$Target'. Run ./make.ps1 help for the list."
        exit 1
    }
}
