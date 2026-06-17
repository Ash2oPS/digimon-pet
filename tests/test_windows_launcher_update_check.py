from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_launcher_reads_background_fetch_result_before_pending_check():
    script = (ROOT / "packaging" / "windows" / "launcher_update_check.ps1").read_text(encoding="utf-8")

    assert "$script:launcherFetchResult = Invoke-Git" in script
    assert "$fetchResult = $script:launcherFetchResult" in script
    assert script.index("$fetchResult = $script:launcherFetchResult") < script.index('"rev-list", "--count"')


def test_windows_launcher_requests_restart_after_successful_pull():
    script = (ROOT / "packaging" / "windows" / "launcher_update_check.ps1").read_text(encoding="utf-8")
    launcher = (ROOT / "Digimon Pet.bat").read_text(encoding="utf-8")

    assert 'Invoke-Git @("pull", "--ff-only", "origin", $localBranch)' in script
    assert "exit 10" in script
    assert script.index('Invoke-Git @("pull", "--ff-only", "origin", $localBranch)') < script.index("exit 10")
    assert 'if "%UPDATE_EXIT_CODE%"=="10"' in launcher
    assert 'call "%~f0" %*' in launcher


def test_windows_launcher_falls_back_to_origin_branch_without_upstream():
    script = (ROOT / "packaging" / "windows" / "launcher_update_check.ps1").read_text(encoding="utf-8")

    assert "Get-UpdateBranch" in script
    assert 'Invoke-Git @("rev-parse", "--abbrev-ref", "HEAD")' in script
    assert '"origin/$($currentBranch.Output.Trim())"' in script
    assert 'Invoke-Git @("rev-list", "--count", "HEAD..$($updateBranch.RemoteBranch)")' in script
    assert 'Invoke-Git @("pull", "--ff-only", "origin", $localBranch)' in script
