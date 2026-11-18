# alice-brain: laptop-as-hotspot stand for Yandex Station Lite (YNDX-00025)
# Adds hosts-based DNS spoof for hotspot clients, opens firewall for the
# unlock server (ports 53/80/443), turns on the Windows Mobile Hotspot.
# Self-elevates via UAC. Cleanup: powershell -File alice_hotspot.ps1 -Cleanup
param([switch]$Cleanup)

$ErrorActionPreference = "Continue"
$logPath = Join-Path $env:USERPROFILE ".alice-tools\hotspot.log"
New-Item -ItemType Directory -Force -Path (Split-Path $logPath) | Out-Null
Start-Transcript -Path $logPath -Force
Write-Host "== alice-brain: laptop hotspot stand =="

$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $argz = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $PSCommandPath)
    if ($Cleanup) { $argz += "-Cleanup" }
    Start-Process powershell -Verb RunAs -ArgumentList $argz
    exit
}

$h = Join-Path $env:SystemRoot "System32\drivers\etc\hosts"
$mark = "# ALICE-BRAIN BEGIN"
$markEnd = "# ALICE-BRAIN END"
$entry = "192.168.137.1 quasar.yandex.net quasar.yandex.ru scbh.yandex.net"

if ($Cleanup) {
    Write-Host "cleanup: removing hosts entries..."
    if (Test-Path $h) {
        $out = New-Object System.Collections.Generic.List[string]
        $inBlock = $false
        foreach ($l in (Get-Content $h)) {
            if ($l -like "*ALICE-BRAIN BEGIN*") { $inBlock = $true; continue }
            if ($l -like "*ALICE-BRAIN END*") { $inBlock = $false; continue }
            if (-not $inBlock) { $out.Add($l) }
        }
        Set-Content -Path $h -Value $out -Encoding ASCII
    }
    ipconfig /flushdns | Out-Null
    netsh advfirewall firewall delete rule name="alice-brain-stand" | Out-Null
    netsh advfirewall firewall delete rule name="alice-brain-stand-dns" | Out-Null
    Write-Host "cleanup: turning hotspot off..."
    try {
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        $cp = [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetInternetConnectionProfile()
        $mgr = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile($cp)
        if ($mgr.TetheringOperationalState -eq [Windows.Networking.NetworkOperators.TetheringOperationalState]::Operational) {
            $op = $mgr.StopTetheringAsync()
            while ($op.Status -eq 0) { Start-Sleep -Milliseconds 200 }
        }
    } catch { Write-Host ("hotspot stop: " + $_.Exception.Message) }
    Write-Host "CLEANUP-DONE"
    exit
}

Write-Host "step 1/3: firewall rules for the unlock stand..."
netsh advfirewall firewall delete rule name="alice-brain-stand" | Out-Null
netsh advfirewall firewall add rule name="alice-brain-stand" dir=in action=allow protocol=TCP localport=80,443 profile=any | Out-Null
netsh advfirewall firewall delete rule name="alice-brain-stand-dns" | Out-Null
netsh advfirewall firewall add rule name="alice-brain-stand-dns" dir=in action=allow protocol=UDP localport=53 profile=any | Out-Null

Write-Host "step 2/3: hosts DNS spoof (quasar.yandex.net -> 192.168.137.1)..."
if (Test-Path $h) {
    $content = Get-Content $h -Raw
    if ($content -notlike "*$mark*") {
        $block = "$mark`r`n$entry`r`n$markEnd"
        Add-Content -Path $h -Value $block -Encoding ASCII
        Write-Host "hosts: added"
    } else {
        Write-Host "hosts: already present"
    }
    ipconfig /flushdns | Out-Null
}

Write-Host "step 3/3: starting mobile hotspot..."
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $cp = [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetInternetConnectionProfile()
    if (-not $cp) {
        Write-Host "ERROR: laptop has no internet connection profile - connect to Wi-Fi first"
        exit 1
    }
    $mgr = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]::CreateFromConnectionProfile($cp)
    $cfg = $mgr.GetCurrentAccessPointConfiguration()
    try { $cfg.Ssid = "alice-setup"; Write-Host "ssid set: alice-setup" } catch { Write-Host ("ERROR ssid: " + $_.Exception.Message) }
    try { $cfg.Passphrase = "alice12345"; Write-Host "pass set: alice12345" } catch { Write-Host ("ERROR pass: " + $_.Exception.Message) }
    try {
        $cfg.Band = [Windows.Networking.NetworkOperators.TetheringWiFiBand]::TwoPointFourGigahertz
        Write-Host "band set: 2.4 GHz"
    } catch {
        try { Write-Host ("band now: " + $cfg.Band) } catch {}
        Write-Host "WARN: band not set - if speaker does not see alice-setup, set 2.4 GHz manually"
    }
    $op = $mgr.ConfigureAccessPointAsync($cfg)
    while ($op.Status -eq 0) { Start-Sleep -Milliseconds 200 }
    if ($mgr.TetheringOperationalState -ne [Windows.Networking.NetworkOperators.TetheringOperationalState]::Operational) {
        $st = $mgr.StartTetheringAsync()
        while ($st.Status -eq 0) { Start-Sleep -Milliseconds 200 }
        $res = $st.GetResults()
        Write-Host ("hotspot start status: " + [int]$res.Status + " (0 = ok)")
        if ([int]$res.Status -ne 0) {
            Write-Host "ERROR: hotspot did not start - turn on Mobile hotspot manually:"
            Write-Host "Settings > Network > Mobile hotspot > On, then rerun installer"
        }
    } else {
        Write-Host "hotspot already running"
    }
    Write-Host ("SSID: " + $cfg.Ssid + " / pass: " + $cfg.Passphrase)
} catch {
    Write-Host ("ERROR: " + $_.Exception.Message)
    Write-Host "hint: turn on hotspot manually (Settings > Network > Mobile hotspot), then rerun"
    Stop-Transcript | Out-Null
    exit 1
}
Write-Host "ALICE-HOTSPOT-READY"
Stop-Transcript | Out-Null
