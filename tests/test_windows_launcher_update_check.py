from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_launcher_reads_background_fetch_result_before_pending_check():
    script = (ROOT / "packaging" / "windows" / "launcher_update_check.ps1").read_text(encoding="utf-8")

    assert "$script:launcherFetchResult = Invoke-Git" in script
    assert "$fetchResult = $script:launcherFetchResult" in script
    assert script.index("$fetchResult = $script:launcherFetchResult") < script.index(
        'Invoke-Git @("rev-list", "--count", "HEAD..@{u}")'
    )


def test_windows_launcher_requests_restart_after_successful_pull():
    script = (ROOT / "packaging" / "windows" / "launcher_update_check.ps1").read_text(encoding="utf-8")
    launcher = (ROOT / "Digimon Pet.bat").read_text(encoding="utf-8")

    assert 'Invoke-Git @("pull", "--ff-only")' in script
    assert "exit 10" in script
    assert script.index('Invoke-Git @("pull", "--ff-only")') < script.index("exit 10")
    assert 'if "%UPDATE_EXIT_CODE%"=="10"' in launcher
    assert 'call "%~f0" %*' in launcher
