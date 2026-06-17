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

try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        exit 0
    }

    if (-not (Test-GitRepository)) {
        exit 0
    }

    $upstream = Invoke-Git @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if ($upstream.ExitCode -ne 0) {
        exit 0
    }

    $splash = New-SplashForm
    $fetchResult = $null
    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 100

    $splash.Add_Shown({
        $script:fetchProcess = [System.ComponentModel.BackgroundWorker]::new()
        $script:fetchProcess.DoWork += {
            $script:fetchResult = Invoke-Git @("fetch", "--quiet", "--prune")
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

    if ($null -eq $fetchResult -or $fetchResult.ExitCode -ne 0) {
        exit 0
    }

    $pending = Invoke-Git @("rev-list", "--count", "HEAD..@{u}")
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

    $pull = Invoke-Git @("pull", "--ff-only")
    if ($pull.ExitCode -ne 0) {
        Show-Notice "La mise a jour Git a echoue. Le jeu va demarrer avec la version locale.`n`n$($pull.Output)" "Mise a jour impossible"
    }
}
catch {
    exit 0
}
