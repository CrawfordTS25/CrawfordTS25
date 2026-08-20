<#
.SYNOPSIS
    Sorts Quantum View exports into Morning QV and Afternoon QV.

.DESCRIPTION
    Files land in Archive. This copies each one into "Morning QV\" or
    "Afternoon QV\" based on the time it was written, and leaves the original in
    Archive untouched.

    ARCHIVE IS THE SOURCE OF TRUTH. The model reads Archive and nothing else, so
    the run folders are a convenience for people browsing the share. That is the
    whole reason this copies rather than moves: if this script fails, is
    disabled, or double-fires, the dashboard is unaffected. Nothing here can cost
    you data - it never writes to, moves from, or deletes anything in Archive.

    Uses the four folders you already have:

        Archive\        landing zone, and what the model reads
        Morning QV\     copies, before the cutoff
        Afternoon QV\   copies, at or after it
        Processed\      _processed.csv - what has been handled, so re-runs are cheap
        Failed\         a COPY of anything that could not be handled, plus why

    Safe to run as often as you like. It skips anything already recorded in the
    manifest, so a schedule that overlaps a manual run does no harm.

.PARAMETER Root
    QV_Data. UNC by default and you should keep it that way - see the scheduling
    notes at the bottom. X: is not mapped inside a scheduled task.

.PARAMETER CutoffHour / CutoffMinute
    Files written before this local time are Morning, at or after it Afternoon.
    Default 13:30. THIS MUST MATCH THE MODEL - section 1 of model-fixes-v3.pq
    uses the same 13:30. Change one and you must change the other, or the share
    and the dashboard will disagree about which run a file belongs to.

.PARAMETER WhatIf
    Show what would be copied without copying anything. Run this first.

.EXAMPLE
    .\qv-file-automation.ps1 -WhatIf
    .\qv-file-automation.ps1
    .\qv-file-automation.ps1 -Verbose
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    # UNC, not X:. A scheduled task running as the service account has no mapped
    # drives - drive letters are per-logon-session, so X:\ resolves to nothing.
    [string] $Root = '\\nfpgshare-1.edwardjones.com\export\support_services\Administrative Services-Solutions\Power BI Reporting\Report Data\QV_Data',

    [int]    $CutoffHour   = 13,
    [int]    $CutoffMinute = 30,
    [string] $Pattern      = '*.csv',

    # A file still being written by the exporter has a size that changes between
    # two looks. Copying mid-write yields a truncated CSV that Power Query will
    # happily load as a short day. This waits it out.
    [int]    $SettleSeconds = 5,

    # 0 = keep run-folder copies forever. Archive is never pruned regardless.
    [int]    $RetentionDays = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Archive   = Join-Path $Root 'Archive'
$Morning   = Join-Path $Root 'Morning QV'
$Afternoon = Join-Path $Root 'Afternoon QV'
$Processed = Join-Path $Root 'Processed'
$Failed    = Join-Path $Root 'Failed'
$LogDir    = Join-Path $Root '_logs'

$LogFile   = Join-Path $LogDir    ('qv-sort-{0:yyyyMM}.log' -f (Get-Date))
$Manifest  = Join-Path $Processed '_processed.csv'

$script:Counts = @{ Copied = 0; Skipped = 0; Unsettled = 0; Failed = 0 }
$script:Seen   = @{}


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
    foreach ($d in @($Archive, $Morning, $Afternoon, $Processed, $Failed, $LogDir)) {
        if (-not (Test-Path -LiteralPath $d)) {
            New-Item -ItemType Directory -Path $d -Force | Out-Null
            Write-Log "created $d"
        }
    }
    if (-not (Test-Path -LiteralPath $Manifest)) {
        'FileName,Length,LastWriteTime,RunWindow,CopiedAt' |
            Set-Content -LiteralPath $Manifest -Encoding UTF8
        Write-Log "created $Manifest"
    }
}


function Read-Manifest {
    <# Keyed on name + size + write time, so a genuinely different file with a
       recycled name is still treated as new. #>
    try {
        Import-Csv -LiteralPath $Manifest | ForEach-Object {
            $script:Seen['{0}|{1}|{2}' -f $_.FileName, $_.Length, $_.LastWriteTime] = $true
        }
        Write-Log "$($script:Seen.Count) file(s) already processed"
    }
    catch { Write-Log "manifest unreadable, treating everything as new: $($_.Exception.Message)" 'WARN' }
}


function Get-Key {
    param([System.IO.FileInfo] $File)
    '{0}|{1}|{2:yyyy-MM-ddTHH:mm:ss}' -f $File.Name, $File.Length, $File.LastWriteTime
}


function Add-ToManifest {
    param([System.IO.FileInfo] $File, [string] $Window)
    '{0},{1},{2:yyyy-MM-ddTHH:mm:ss},{3},{4:yyyy-MM-ddTHH:mm:ss}' -f
        $File.Name, $File.Length, $File.LastWriteTime, $Window, (Get-Date) |
        Add-Content -LiteralPath $Manifest -Encoding UTF8
}


function Test-Settled {
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
    if ($Written -lt $cutoff) { 'Morning QV' } else { 'Afternoon QV' }
}


function Move-ToFailed {
    <# A COPY, never a move. Archive stays whole; Failed is for someone to look
       at without going near the source of truth. #>
    param([System.IO.FileInfo] $File, [string] $Reason)
    $dest = Join-Path $Failed ('{0:yyyy-MM-dd_HHmmss}_{1}' -f (Get-Date), $File.Name)
    try {
        if ($PSCmdlet.ShouldProcess($dest, 'Copy to Failed')) {
            Copy-Item -LiteralPath $File.FullName -Destination $dest -Force
            "$Reason" | Set-Content -LiteralPath ($dest + '.reason.txt') -Encoding UTF8
        }
    } catch { }
    Write-Log "FAILED $($File.Name): $Reason" 'ERROR'
    $script:Counts.Failed++
}


function Copy-ToRunFolder {
    param([System.IO.FileInfo] $File, [string] $Window)

    $target   = if ($Window -eq 'Morning QV') { $Morning } else { $Afternoon }
    $destName = '{0:yyyy-MM-dd}_{1}{2}' -f $File.LastWriteTime, $File.BaseName, $File.Extension
    $dest     = Join-Path $target $destName

    if (Test-Path -LiteralPath $dest) {
        $existing = Get-Item -LiteralPath $dest
        if ($existing.Length -eq $File.Length -and
            [math]::Abs(($existing.LastWriteTime - $File.LastWriteTime).TotalSeconds) -lt 2) {
            Add-ToManifest -File $File -Window $Window   # catch the manifest up
            $script:Counts.Skipped++
            Write-Verbose "already in place: $destName"
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
        Add-ToManifest -File $File -Window $Window
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
    Read-Manifest
    Write-Log ("start  root={0}  cutoff={1:00}:{2:00}" -f $Root, $CutoffHour, $CutoffMinute)

    $files = Get-ChildItem -LiteralPath $Archive -File -Filter $Pattern |
             Where-Object { -not $_.Name.StartsWith('~$') } |
             Sort-Object LastWriteTime

    Write-Log "$($files.Count) file(s) in Archive"

    foreach ($f in $files) {
        try {
            if ($script:Seen.ContainsKey((Get-Key $f))) {
                $script:Counts.Skipped++
                Write-Verbose "skip (in manifest): $($f.Name)"
                continue
            }
            if ($f.Length -eq 0) {
                Move-ToFailed -File $f -Reason 'zero bytes'
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
            Move-ToFailed -File $f -Reason $_.Exception.Message
        }
    }

    Remove-OldRunCopies

    Write-Log ("done  copied={0} skipped={1} unsettled={2} failed={3}" -f
               $Counts.Copied, $Counts.Skipped, $Counts.Unsettled, $Counts.Failed)

    # Non-zero exit makes Task Scheduler show the run as failed, which is what you
    # want a monitored task to do when it could not do its job.
    if ($Counts.Failed -gt 0) { exit 1 }
    exit 0
}
catch {
    Write-Log "FATAL: $($_.Exception.Message)" 'ERROR'
    exit 2
}


<#
YOUR FOLDERS
============
    \\nfpgshare-1.edwardjones.com\export\support_services\
        Administrative Services-Solutions\Power BI Reporting\Report Data\QV_Data\
            Archive\                        <- exports land here. THE MODEL READS THIS.
            Morning QV\                     <- copies, for people
            Afternoon QV\                   <- copies, for people
            Processed\_processed.csv        <- state, so re-runs are cheap
            Failed\                         <- copies of problems, plus a .reason.txt
            _logs\                          <- one log per month
            QV_Automation_Helper_Lists.xlsx <- not touched by this script

X: is the same place. Use UNC here; see below.

SCHEDULING IT
=============
Run once as yourself with -WhatIf, then once for real, then schedule.

  1. Task Scheduler > Create Task (not Basic Task)
  2. General
       Name: QV export sort
       Run whether user is logged on or not
       Run with highest privileges: not needed
       ACCOUNT: the SERVICE ACCOUNT, not your login. Same rule as the gateway
       credentials - tie it to you and it stops the day you change roles.
  3. Triggers - two, sitting after each export lands:
       Daily 09:00
       Daily 15:00
       Tick "Repeat task every 30 minutes for 2 hours" on each, so a late export
       is picked up without waiting for tomorrow.
  4. Actions > Start a program
       Program:   powershell.exe
       Arguments: -NoProfile -ExecutionPolicy Bypass -File "\\nfpgshare-1.edwardjones.com\export\support_services\Administrative Services-Solutions\Power BI Reporting\Report Data\QV_Data\_scripts\qv-file-automation.ps1"
  5. Settings
       If the task fails, restart every 5 minutes, up to 3 times
       Stop the task if it runs longer than 1 hour

  USE UNC PATHS, NOT X:. Drive letters are mapped per logon session. A task
  running as the service account with nobody logged on has no X:, and the task
  fails instantly with a path-not-found that looks like a permissions problem
  and is not.

  The service account needs READ on Archive and WRITE on Morning QV, Afternoon
  QV, Processed, Failed and _logs. It does NOT need write access to Archive -
  this script never modifies it.

CHECKING IT WORKED
==================
    Get-Content "\\...\QV_Data\_logs\qv-sort-$(Get-Date -f yyyyMM).log" -Tail 20

A healthy run reads  copied=2 skipped=N unsettled=0 failed=0  where N grows as
the manifest fills. unsettled>0 twice running means the exporter is slower than
SettleSeconds - raise it. failed>0 is almost always permissions on a destination,
and Failed\*.reason.txt will say which.
#>
