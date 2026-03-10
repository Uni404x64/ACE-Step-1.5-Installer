# ACE-Step 1.5 Complete Installer -- One click. Done.

param(
    [string]$ModelsSource = "",
    [switch]$SkipModelCheck
)

# Self-elevate to admin if not already
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]"Administrator")) {
    $argList = "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    if ($ModelsSource) { $argList += " -ModelsSource `"$ModelsSource`"" }
    if ($SkipModelCheck) { $argList += " -SkipModelCheck" }
    Start-Process PowerShell -ArgumentList $argList -Verb RunAs
    exit
}

$ErrorActionPreference = "Stop"
$ProgressPreference = 'SilentlyContinue'

Write-Host ""
Write-Host "=== ACE-Step 1.5 Installer ===" -ForegroundColor Cyan

# ==============================================================
# STEP 1: Find or clone repo
# ==============================================================
Write-Host ""
Write-Host "[1/5] Locating ACE-Step 1.5..." -ForegroundColor Yellow

$checkPaths = @(
    "$env:USERPROFILE\ACE-Step-1.5",
    "$env:USERPROFILE\Downloads\ACE-Step-1.5"
)

$InstallPath = $null
foreach ($p in $checkPaths) {
    if (Test-Path "$p\.git") {
        $InstallPath = $p
        Write-Host "  [OK] Found existing install at: $InstallPath" -ForegroundColor Green
        break
    }
}

# ==============================================================
# STEP 2: Check/Install UV
# ==============================================================
Write-Host ""
Write-Host "[2/5] Checking UV package manager..." -ForegroundColor Yellow

$uvExists = $null
try { $uvExists = Get-Command uv -ErrorAction Stop } catch {}

if (-not $uvExists) {
    Write-Host "  -> UV not found, installing..." -ForegroundColor Gray
    try {
        Invoke-Expression "& { $(Invoke-RestMethod https://astral.sh/uv/install.ps1) }"
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        Write-Host "  [OK] UV installed" -ForegroundColor Green
    } catch {
        Write-Host "  [FAIL] Failed to install UV: $_" -ForegroundColor Red
        Write-Host "  Manual install: https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Yellow
        pause
        exit 1
    }
} else {
    Write-Host "  [OK] UV found: $(uv --version)" -ForegroundColor Green
}

# ==============================================================
# STEP 2b: Clone if not found
# ==============================================================
if (-not $InstallPath) {
    Write-Host ""
    Write-Host "  -> No existing install found, cloning repo..." -ForegroundColor Gray

    $gitExists = $null
    try { $gitExists = Get-Command git -ErrorAction Stop } catch {}

    if (-not $gitExists) {
        Write-Host "  [FAIL] Git not found!" -ForegroundColor Red
        Write-Host "  Download from: https://git-scm.com/download/win" -ForegroundColor Yellow
        Write-Host "  After installing Git, run this script again." -ForegroundColor Yellow
        pause
        exit 1
    }

    $InstallPath = "$env:USERPROFILE\ACE-Step-1.5"
    Write-Host "  -> Cloning to: $InstallPath" -ForegroundColor Gray
    git clone https://github.com/ace-step/ACE-Step-1.5.git $InstallPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [FAIL] Git clone failed (exit code $LASTEXITCODE)" -ForegroundColor Red
        pause
        exit 1
    }
    Write-Host "  [OK] Cloned" -ForegroundColor Green
}

Set-Location $InstallPath

# ==============================================================
# STEP 3: Install dependencies
# ==============================================================
Write-Host ""
Write-Host "[3/5] Installing dependencies..." -ForegroundColor Yellow
Write-Host "  (This may take a few minutes on first run)" -ForegroundColor Gray

uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] UV sync failed (exit code $LASTEXITCODE)" -ForegroundColor Red
    pause
    exit 1
}
Write-Host "  [OK] Dependencies installed" -ForegroundColor Green

# Launcher GUI deps
Write-Host "  Installing launcher dependencies..." -ForegroundColor Gray
uv pip install customtkinter pystray Pillow psutil --quiet

# Pin torchao to 0.14.1 -- 0.15.0 is incompatible with torch 2.7.1
# and causes uv to uninstall/reinstall it on EVERY single launch
Write-Host "  Pinning torchao to avoid reinstall-on-every-launch bug..." -ForegroundColor Gray
uv pip install "torchao==0.14.1" --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] torchao pinned" -ForegroundColor Green
} else {
    Write-Host "  [!] torchao pin failed - you'll see reinstall spam on each launch (harmless)" -ForegroundColor Yellow
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [!] Launcher deps failed - GUI may not work, continuing anyway." -ForegroundColor Yellow
} else {
    Write-Host "  [OK] Launcher dependencies installed" -ForegroundColor Green
}

# Copy launcher.py to install root (next to pyproject.toml)
$launcherSrc = Join-Path $PSScriptRoot "launcher.py"
$launcherDst = Join-Path $InstallPath "launcher.py"
if (Test-Path $launcherSrc) {
    Copy-Item $launcherSrc $launcherDst -Force
    Write-Host "  [OK] launcher.py placed at install root" -ForegroundColor Green
} else {
    Write-Host "  [!] launcher.py not found in installer folder." -ForegroundColor Yellow
}

# Copy webui folder -- any .html files the installer ships
$webuiSrc = Join-Path (Split-Path $PSScriptRoot -Parent) "webui"
$webuiDst = Join-Path $InstallPath "webui"
if (Test-Path $webuiSrc) {
    if (-not (Test-Path $webuiDst)) {
        New-Item -Path $webuiDst -ItemType Directory -Force | Out-Null
    }
    $htmlFiles = Get-ChildItem $webuiSrc -Filter '*.html' -ErrorAction SilentlyContinue
    foreach ($f in $htmlFiles) {
        Copy-Item $f.FullName (Join-Path $webuiDst $f.Name) -Force
    }
    $count = ($htmlFiles | Measure-Object).Count
    if ($count -gt 0) {
        Write-Host "  [OK] $count WebUI file(s) copied to /webui/" -ForegroundColor Green
    } else {
        Write-Host "  [!] No .html files found in installer/webui/ folder." -ForegroundColor Yellow
    }
} else {
    # Create empty webui dir so launcher doesn't complain
    if (-not (Test-Path $webuiDst)) {
        New-Item -Path $webuiDst -ItemType Directory -Force | Out-Null
    }
    Write-Host "  [!] No webui folder in installer package -- created empty /webui/ dir." -ForegroundColor Yellow
}

# Write .env config - pick LM model based on VRAM
Write-Host "  Detecting GPU VRAM..." -ForegroundColor Gray
$vramGB = 0
$gpuName = ""

# Try nvidia-smi first (most accurate, handles >4GB, supports multi-GPU)
try {
    $smiLines = & nvidia-smi --query-gpu=memory.total,name --format=csv,noheader,nounits 2>$null
    $bestMB = 0
    foreach ($line in $smiLines) {
        if ($line -match '^\s*(\d+)\s*,\s*(.+)$') {
            $mb = [int]$Matches[1]
            $name = $Matches[2].Trim()
            if ($mb -gt $bestMB) {
                $bestMB = $mb
                $gpuName = $name
            }
        }
    }
    if ($bestMB -gt 0) {
        $vramGB = [math]::Round($bestMB / 1024, 1)
    }
} catch {}

# Fallback to WMI if nvidia-smi unavailable — sort by VRAM descending, pick largest
if ($vramGB -eq 0) {
    try {
        $bestGpu = Get-CimInstance -ClassName Win32_VideoController |
            Where-Object { $_.AdapterRAM -gt 0 } |
            Sort-Object AdapterRAM -Descending |
            Select-Object -First 1
        if ($bestGpu) {
            $vramGB = [math]::Round($bestGpu.AdapterRAM / 1GB, 1)
            $gpuName = $bestGpu.Name
        }
    } catch {}
}

if ($vramGB -ge 12) {
    $lmModel = "acestep-5Hz-lm-1.7B"
    $gpuInfo = if ($gpuName) { "$gpuName - ${vramGB}GB" } else { "${vramGB}GB VRAM" }
    Write-Host "  [OK] $gpuInfo detected - using 1.7B LM model" -ForegroundColor Green
} else {
    $lmModel = "acestep-5Hz-lm-0.6B"
    if ($vramGB -gt 0) {
        $gpuInfo = if ($gpuName) { "$gpuName - ${vramGB}GB" } else { "${vramGB}GB VRAM" }
        Write-Host "  [OK] $gpuInfo detected - using 0.6B LM model (1.7B needs 12GB+)" -ForegroundColor Yellow
    } else {
        Write-Host "  [!] Couldn't detect VRAM - defaulting to 0.6B LM model (safe for 8GB)" -ForegroundColor Yellow
    }
}

Write-Host "  Writing .env config..." -ForegroundColor Gray
$envLines = @(
    "ACESTEP_CONFIG_PATH=acestep-v15-turbo",
    "ACESTEP_LM_MODEL_PATH=$lmModel",
    "ACESTEP_DEVICE=auto",
    "ACESTEP_LM_BACKEND=pt",
    "ACESTEP_INIT_LLM=auto",
    "NO_PROXY=127.0.0.1,localhost",
    "no_proxy=127.0.0.1,localhost"
)
$envLines | Out-File -FilePath "$InstallPath\.env" -Encoding UTF8
Write-Host "  [OK] .env written (LM: $lmModel)" -ForegroundColor Green

# Remove any LM checkpoint dir that has no actual weights (causes init crash)
$weightFileNames = @('model.safetensors', 'pytorch_model.bin', 'tf_model.h5', 'model.ckpt.index', 'flax_model.msgpack')
foreach ($lmDir in @("$InstallPath\checkpoints\acestep-5Hz-lm-0.6B", "$InstallPath\checkpoints\acestep-5Hz-lm-1.7B")) {
    if (Test-Path $lmDir) {
        $hasWeights = $false
        foreach ($wf in $weightFileNames) {
            if (Test-Path "$lmDir\$wf") { $hasWeights = $true; break }
        }
        # Also check for sharded safetensors (model-00001-of-XXXXX.safetensors)
        if (-not $hasWeights) {
            $shards = Get-ChildItem $lmDir -Filter 'model-*.safetensors' -ErrorAction SilentlyContinue
            if ($shards.Count -gt 0) { $hasWeights = $true }
        }
        if (-not $hasWeights) {
            Remove-Item $lmDir -Recurse -Force
            $dirName = Split-Path $lmDir -Leaf
            Write-Host "  [OK] Removed empty/broken dir: $dirName" -ForegroundColor Green
        }
    }
}

# ==============================================================
# STEP 4: Models
# ==============================================================
Write-Host ""
Write-Host "[4/5] Checking models..." -ForegroundColor Yellow

if (-not $SkipModelCheck) {
    Clear-Host
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host "              MODEL DOWNLOAD" -ForegroundColor Yellow
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Models are ~9GB total." -ForegroundColor White
    Write-Host ""
    Write-Host "  [1] Download now  (~9GB, recommended)" -ForegroundColor Green
    Write-Host "      Resumes automatically if interrupted." -ForegroundColor DarkGreen
    Write-Host ""
    Write-Host "  [2] Skip for now  (downloads on first launch)" -ForegroundColor Gray
    Write-Host "      No resume if interrupted later." -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
    $choice = Read-Host "  >>> Choose 1 or 2 (Enter = 2)"

    if ($choice -eq "1") {
        Write-Host ""
        Write-Host "  -> Downloading models..." -ForegroundColor Cyan
        uv run acestep-download
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] Models downloaded" -ForegroundColor Green
        } else {
            Write-Host "  [!] Download stopped or incomplete. Run installer again to resume." -ForegroundColor Yellow
        }
    } else {
        Write-Host "  -> Skipping. Models will auto-download on first launch." -ForegroundColor Gray
    }
}

# ==============================================================
# STEP 5: Desktop shortcut (one launcher)
# ==============================================================
Write-Host ""
Write-Host "[5/5] Creating desktop shortcut..." -ForegroundColor Yellow

try {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $wsh = New-Object -ComObject WScript.Shell

    # Remove old generic shortcuts if present
    @(
        "$desktop\ACE-Step Gradio UI.lnk",
        "$desktop\ACE-Step WebUI.lnk",
        "$desktop\ACE-Step API Server.lnk",
        "$desktop\ACE-Step Gradio.lnk",
        "$desktop\ACE-Step API.lnk"
    ) | ForEach-Object {
        if (Test-Path $_) { Remove-Item $_ -Force }
    }

    if (Test-Path $launcherDst) {
        $uvPath = (Get-Command uv -ErrorAction SilentlyContinue).Source
        $sc = $wsh.CreateShortcut("$desktop\ACE-Step 1.5.lnk")
        if ($uvPath) {
            $sc.TargetPath = $uvPath
            $sc.Arguments  = "run python `"$launcherDst`""
        } else {
            $sc.TargetPath = "pythonw.exe"
            $sc.Arguments  = "`"$launcherDst`""
        }
        $sc.WorkingDirectory = $InstallPath
        $sc.Description = "ACE-Step 1.5 Launcher"
        $sc.Save()
        Write-Host "  [OK] Desktop shortcut created: ACE-Step 1.5.lnk" -ForegroundColor Green
    } else {
        Write-Host "  [!] launcher.py missing - no shortcut created." -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [!] Shortcut creation failed: $_" -ForegroundColor Yellow
}

# ==============================================================
# DONE
# ==============================================================
Write-Host ""
Write-Host "  ============================================" -ForegroundColor Green
Write-Host "          INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "  ============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Installed to: $InstallPath" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Double-click 'ACE-Step 1.5' on your desktop to launch." -ForegroundColor Cyan
Write-Host "  First launch downloads models (~9GB) if not already present." -ForegroundColor Gray
Write-Host ""
Write-Host "  --------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Everything lives in $InstallPath now." -ForegroundColor Gray
Write-Host "  You can safely delete this installer folder." -ForegroundColor Gray
Write-Host "  It's served its purpose. Let it rest." -ForegroundColor DarkGray
Write-Host "  --------------------------------------------" -ForegroundColor DarkGray
Write-Host ""

pause