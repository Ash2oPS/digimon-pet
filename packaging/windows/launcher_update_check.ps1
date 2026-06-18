Set-StrictMode -Version Latest

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

function Show-Notice {
    param(
        [string] $Message,
        [string] $Title = "Digimon Pet"
    )

    [System.Windows.Forms.MessageBox]::Show(
        $Message,
        $Title,
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
}

function Ask-YesNo {
    param(
        [string] $Message,
        [string] $Title = "Digimon Pet"
    )

    $answer = [System.Windows.Forms.MessageBox]::Show(
        $Message,
        $Title,
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )

    return $answer -eq [System.Windows.Forms.DialogResult]::Yes
}

function Invoke-Git {
    param([string[]] $Arguments)

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "git"
    foreach ($argument in $Arguments) {
        [void] $psi.ArgumentList.Add($argument)
    }
    $psi.WorkingDirectory = $repoRoot
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $process = [System.Diagnostics.Process]::Start($psi)
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        Output = ($stdout + $stderr).Trim()
    }
}

function New-SplashForm {
    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Digimon Pet"
    $form.StartPosition = "CenterScreen"
    $form.FormBorderStyle = "FixedDialog"
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.ControlBox = $false
    $form.ClientSize = New-Object System.Drawing.Size(330, 105)
    $form.TopMost = $true

    $title = New-Object System.Windows.Forms.Label
    $title.Text = "Chargement de Digimon Pet..."
    $title.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
    $title.AutoSize = $true
    $title.Location = New-Object System.Drawing.Point(22, 18)
    [void] $form.Controls.Add($title)

    $status = New-Object System.Windows.Forms.Label
    $status.Text = "Verification des mises a jour Git"
    $status.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    $status.AutoSize = $true
    $status.Location = New-Object System.Drawing.Point(23, 50)
    [void] $form.Controls.Add($status)

    $progress = New-Object System.Windows.Forms.ProgressBar
    $progress.Style = "Marquee"
    $progress.MarqueeAnimationSpeed = 25
    $progress.Location = New-Object System.Drawing.Point(25, 75)
    $progress.Size = New-Object System.Drawing.Size(280, 12)
    [void] $form.Controls.Add($progress)

    return $form
}

function Test-GitRepository {
    $gitDir = Join-Path $repoRoot ".git"
    if (-not (Test-Path $gitDir)) {
        return $false
    }

    $gitCheck = Invoke-Git @("rev-parse", "--is-inside-work-tree")
    return $gitCheck.ExitCode -eq 0
}

function Get-UpdateBranch {
    $currentBranch = Invoke-Git @("rev-parse", "--abbrev-ref", "HEAD")
    if ($currentBranch.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($currentBranch.Output)) {
        return $null
    }

    $localBranch = $currentBranch.Output.Trim()
    if ($localBranch -eq "HEAD") {
        return $null
    }

    $upstream = Invoke-Git @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if ($upstream.ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($upstream.Output)) {
        return [pscustomobject]@{
            LocalBranch = $localBranch
            RemoteBranch = $upstream.Output.Trim()
        }
    }

    $originBranch = "origin/$($currentBranch.Output.Trim())"
    $originCheck = Invoke-Git @("rev-parse", "--verify", "--quiet", $originBranch)
    if ($originCheck.ExitCode -ne 0) {
        return $null
    }

    return [pscustomobject]@{
        LocalBranch = $localBranch
        RemoteBranch = $originBranch
    }
}

function Save-LocalChangesForUpdate {
    $status = Invoke-Git @("status", "--porcelain")
    if ($status.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($status.Output)) {
        return [pscustomobject]@{
            CanContinue = $true
            Stashed = $false
        }
    }

    $shouldStash = Ask-YesNo "Des changements locaux non commit sont presents.`n`nL'updater doit les mettre de cote temporairement pour appliquer la mise a jour, puis les restaurer apres.`n`nContinuer ?" "Changements locaux detectes"
    if (-not $shouldStash) {
        return [pscustomobject]@{
            CanContinue = $false
            Stashed = $false
        }
    }

    $stashMessage = "Digimon Pet auto-stash before update $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $stash = Invoke-Git @("stash", "push", "-u", "-m", $stashMessage)
    if ($stash.ExitCode -ne 0) {
        Show-Notice "Impossible de mettre les changements locaux de cote. La mise a jour est annulee.`n`n$($stash.Output)" "Mise a jour annulee"
        return [pscustomobject]@{
            CanContinue = $false
            Stashed = $false
        }
    }

    return [pscustomobject]@{
        CanContinue = $true
        Stashed = $true
    }
}

function Restore-LocalChangesAfterUpdate {
    param([bool] $Stashed)

    if (-not $Stashed) {
        return
    }

    $restore = Invoke-Git @("stash", "pop")
    if ($restore.ExitCode -ne 0) {
        Show-Notice "La mise a jour est installee, mais les changements locaux n'ont pas pu etre restaures automatiquement.`n`nOuvrez Git/SourceTree pour resoudre le stash ou les conflits avant de modifier le projet.`n`n$($restore.Output)" "Changements locaux a verifier"
    }
}

try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        exit 0
    }

    if (-not (Test-GitRepository)) {
        exit 0
    }

    $splash = New-SplashForm
    $script:launcherFetchResult = $null
    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 100

    $splash.Add_Shown({
        $script:fetchProcess = [System.ComponentModel.BackgroundWorker]::new()
        $script:fetchProcess.DoWork += {
            $script:launcherFetchResult = Invoke-Git @("fetch", "--quiet", "--prune")
        }
        $script:fetchProcess.RunWorkerCompleted += {
            $timer.Stop()
            $splash.Close()
        }
        $script:fetchProcess.RunWorkerAsync()
    })

    $timer.Add_Tick({
        [System.Windows.Forms.Application]::DoEvents()
    })

    $timer.Start()
    [void] $splash.ShowDialog()

    $fetchResult = $script:launcherFetchResult
    if ($null -eq $fetchResult -or $fetchResult.ExitCode -ne 0) {
        exit 0
    }

    $updateBranch = Get-UpdateBranch
    if ($null -eq $updateBranch) {
        exit 0
    }

    $pending = Invoke-Git @("rev-list", "--count", "HEAD..$($updateBranch.RemoteBranch)")
    if ($pending.ExitCode -ne 0) {
        exit 0
    }

    $pendingCount = 0
    if (-not [int]::TryParse($pending.Output.Trim(), [ref] $pendingCount)) {
        exit 0
    }

    if ($pendingCount -le 0) {
        exit 0
    }

    $plural = if ($pendingCount -eq 1) { "commit est disponible" } else { "commits sont disponibles" }
    $shouldUpdate = Ask-YesNo "$pendingCount $plural.`n`nVoulez-vous mettre le jeu a jour avant de le lancer ?" "Mise a jour disponible"
    if (-not $shouldUpdate) {
        exit 0
    }

    $localChanges = Save-LocalChangesForUpdate
    if (-not $localChanges.CanContinue) {
        exit 0
    }

    $localBranch = $updateBranch.LocalBranch
    $pull = Invoke-Git @("pull", "--ff-only", "origin", $localBranch)
    if ($pull.ExitCode -ne 0) {
        Restore-LocalChangesAfterUpdate $localChanges.Stashed
        Show-Notice "La mise a jour Git a echoue. Le jeu va demarrer avec la version locale.`n`n$($pull.Output)" "Mise a jour impossible"
        exit 0
    }

    Restore-LocalChangesAfterUpdate $localChanges.Stashed
    exit 10
}
catch {
    exit 0
}
