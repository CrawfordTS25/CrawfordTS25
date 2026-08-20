<#
.SYNOPSIS
    Sorts Quantum View exports into Morning and Afternoon folders.

.DESCRIPTION
    Files land in Archive. This copies each one into Morning\ or Afternoon\ based
    on the time it was written, and leaves the original in Archive untouched.

    ARCHIVE IS THE SOURCE OF TRUTH. The model reads Archive and nothing else, so
    the run folders are a convenience for people browsing the share. That is the
    whole reason this copies rather than moves: if this script fails, is disabled,
    or double-fires, the dashboard is unaffected. Nothing here can cost you data.

    Safe to run as often as you like. It skips anything already copied, so a
    schedule that overlaps a manual run does no harm.

.PARAMETER Root
    The Quantum View data folder holding Archive, Morning and Afternoon.

.PARAMETER CutoffHour / CutoffMinute
    Files written before this local time are Morning, at or after it Afternoon.
    Default 13:30. THIS MUST MATCH THE MODEL - QV_RAW in model-fixes-v3.pq uses
    the same 13:30. Change one and you must change the other, or the share and the
    dashboard will disagree about which run a file belongs to.

.PARAMETER WhatIf
    Show what would be copied without copying anything. Run this first.

.EXAMPLE
    .\qv-file-automation.ps1 -WhatIf
    .\qv-file-automation.ps1
    .\qv-file-automation.ps1 -Root "\\server\share\Quantum View\QV_Data" -Verbose
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string] $Root = '\\nfpgshare-1.edwardjones.com\export\support_services\Administrative Services-Solutions\Quantum View\QV_Data',
    [int]    $CutoffHour   = 13,
    [int]    $CutoffMinute = 30,
    [string] $Pattern      = '*.csv',
    # A file still being written by the exporter has a size that changes between
    # two looks. Copying mid-write yields a truncated CSV that Power Query will
    # happily load as a short day. This waits it out.
    [int]    $SettleSeconds = 5,
    [int]    $RetentionDays = 0        # 0 = keep run-folder copies forever
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Archive   = Join-Path $Root 'Archive'
$Morning   = Join-Path $Root 'Morning'
$Afternoon = Join-Path $Root 'Afternoon'
$LogDir    = Join-Path $Root '_logs'
$LogFile   = Join-Path $LogDir ('qv-sort-{0:yyyyMM}.log' -f (Get-Date))

$script:Counts = @{ Copied = 0; Skipped = 0; Unsettled = 0; Empty = 0; Failed = 0 }


function Write-Log {
    param([string] $Message, [ValidateSet('INFO','WARN','ERROR')] [string] $Level = 'INFO')
    $line = '{0:yyyy-MM-dd HH:mm:ss}  {1,-5}  {2}' -f (Get-Date), $Level, $Message
    switch ($Level) {
        'ERROR' { Write-Host $line -ForegroundColor Red }
        'WARN'  { Write-Host $line -ForegroundColor Yellow }
        default { Write-Host $line }
    }
    try { Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8 } catch { }
}


function Initialize-Folders {
    foreach ($d in @($Archive, $Morning, $Afternoon, $LogDir)) {
        if (-not (Test-Path -LiteralPath $d)) {
            New-Item -ItemType Directory -Path $d -Force | Out-Null
            Write-Log "created $d"
        }
    }
}


function Test-Settled {
    <# True when the file's size is the same twice in a row, i.e. nobody is
       still writing to it. #>
    param([System.IO.FileInfo] $File)
    $first = $File.Length
    Start-Sleep -Seconds $SettleSeconds
    $File.Refresh()
    return ($File.Length -eq $first)
}


function Get-RunWindow {
    <# Morning before the cutoff, Afternoon at or after it. LastWriteTime, not
       CreationTime: a copied file inherits the write time but gets a fresh
       creation time, so CreationTime would reclassify anything ever re-copied. #>
    param([datetime] $Written)
    $cutoff = [datetime]::new($Written.Year, $Written.Month, $Written.Day,
                              $CutoffHour, $CutoffMinute, 0)
    if ($Written -lt $cutoff) { return 'Morning' } else { return 'Afternoon' }
}


function Copy-ToRunFolder {
    param([System.IO.FileInfo] $File, [string] $Window)

    $target    = if ($Window -eq 'Morning') { $Morning } else { $Afternoon }
    $dated     = '{0:yyyy-MM-dd}' -f $File.LastWriteTime
    $destName  = '{0}_{1}{2}' -f $dated, $File.BaseName, $File.Extension
    $dest      = Join-Path $target $destName

    # Already there and the same file? Nothing to do. Comparing write time AND
    # length is enough here - these are same-day exports from one producer, so a
    # hash would cost minutes across a full Archive for no extra certainty.
    if (Test-Path -LiteralPath $dest) {
        $existing = Get-Item -LiteralPath $dest
        if ($existing.Length -eq $File.Length -and
            [math]::Abs(($existing.LastWriteTime - $File.LastWriteTime).TotalSeconds) -lt 2) {
            $script:Counts.Skipped++
            Write-Verbose "skip (already copied): $destName"
            return
        }
        # Same name, different content. Never overwrite - keep both and say so.
        $dest = Join-Path $target ('{0}_{1:HHmmss}{2}' -f
                    [IO.Path]::GetFileNameWithoutExtension($destName),
                    $File.LastWriteTime, $File.Extension)
        Write-Log "name collision with different content, writing as $(Split-Path $dest -Leaf)" 'WARN'
    }

    if ($PSCmdlet.ShouldProcess($dest, 'Copy')) {
        Copy-Item -LiteralPath $File.FullName -Destination $dest -Force
        # Preserve the write time so the run window survives the copy and the
        # model's freshness stamps stay honest.
        (Get-Item -LiteralPath $dest).LastWriteTime = $File.LastWriteTime
        $script:Counts.Copied++
        Write-Log "$Window  <-  $($File.Name)"
    }
}


function Remove-OldRunCopies {
    if ($RetentionDays -le 0) { return }
    $cut = (Get-Date).AddDays(-$RetentionDays)
    foreach ($d in @($Morning, $Afternoon)) {
        Get-ChildItem -LiteralPath $d -File -Filter $Pattern |
            Where-Object { $_.LastWriteTime -lt $cut } |
            ForEach-Object {
                if ($PSCmdlet.ShouldProcess($_.FullName, 'Remove')) {
                    Remove-Item -LiteralPath $_.FullName -Force
                    Write-Log "pruned $($_.Name) from $(Split-Path $d -Leaf)"
                }
            }
    }
    # Archive is never pruned. It is the source of truth.
}


# ------------------------------------------------------------------------ main
try {
    Initialize-Folders
    Write-Log "start  root=$Root  cutoff=$('{0:00}:{1:00}' -f $CutoffHour, $CutoffMinute)"

    $files = Get-ChildItem -LiteralPath $Archive -File -Filter $Pattern |
             Where-Object { -not $_.Name.StartsWith('~$') } |
             Sort-Object LastWriteTime

    Write-Log "$($files.Count) file(s) in Archive"

    foreach ($f in $files) {
        try {
            if ($f.Length -eq 0) {
                $script:Counts.Empty++
                Write-Log "zero bytes, skipping: $($f.Name)" 'WARN'
                continue
            }
            if (-not (Test-Settled $f)) {
                $script:Counts.Unsettled++
                Write-Log "still being written, will pick up next run: $($f.Name)" 'WARN'
                continue
            }
            Copy-ToRunFolder -File $f -Window (Get-RunWindow $f.LastWriteTime)
        }
        catch {
            $script:Counts.Failed++
            Write-Log "FAILED $($f.Name): $($_.Exception.Message)" 'ERROR'
        }
    }

    Remove-OldRunCopies

    Write-Log ("done  copied={0} skipped={1} unsettled={2} empty={3} failed={4}" -f
               $Counts.Copied, $Counts.Skipped, $Counts.Unsettled, $Counts.Empty, $Counts.Failed)

    # Non-zero exit makes Task Scheduler show the run as failed, which is what
    # you want a monitored task to do when it could not do its job.
    if ($Counts.Failed -gt 0) { exit 1 }
    exit 0
}
catch {
    Write-Log "FATAL: $($_.Exception.Message)" 'ERROR'
    exit 2
}


<#
SCHEDULING IT
=============
Run once as yourself with -WhatIf, then once for real, then schedule.

    Register-ScheduledJob is not enough - it dies with your session. Use Task
    Scheduler so it survives reboots and runs while nobody is logged in.

  1. Task Scheduler > Create Task (not Basic Task)
  2. General
       Name:  QV export sort
       Run whether user is logged on or not
       Run with highest privileges: NOT needed
       ACCOUNT: use the SERVICE ACCOUNT, not your login. This is the same rule as
       the Power BI gateway credentials - tie it to your account and it stops the
       day you change roles or are on PTO.
  3. Triggers - two of them, sitting after each export lands:
       Daily 09:00
       Daily 15:00
       Tick "Repeat task every 30 minutes for 2 hours" on each, so a late export
       is picked up without waiting for tomorrow.
  4. Actions > Start a program
       Program:   powershell.exe
       Arguments: -NoProfile -ExecutionPolicy Bypass -File "\\path\to\qv-file-automation.ps1"
  5. Settings
       If the task fails, restart every 5 minutes, up to 3 times
       Stop the task if it runs longer than 1 hour

  The service account needs READ on Archive and WRITE on Morning, Afternoon and
  _logs. It does NOT need write access to Archive - this script never modifies it.

FOLDER LAYOUT THIS EXPECTS
==========================
    QV_Data\
        Archive\      <- exports land here. The model reads THIS and only this.
        Morning\      <- copies, for people
        Afternoon\    <- copies, for people
        _logs\        <- one log per month

CHECKING IT WORKED
==================
    Get-Content "\\...\QV_Data\_logs\qv-sort-$(Get-Date -f yyyyMM).log" -Tail 20

A healthy run reads  copied=2 skipped=N unsettled=0 empty=0 failed=0  where N grows
as Archive fills. unsettled>0 twice in a row means the exporter is slower than
SettleSeconds - raise it. failed>0 is almost always a permissions problem on the
destination.
#>
