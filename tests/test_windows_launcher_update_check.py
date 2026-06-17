from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_launcher_reads_background_fetch_result_before_pending_check():
    script = (ROOT / "packaging" / "windows" / "launcher_update_check.ps1").read_text(encoding="utf-8")

    assert "$script:launcherFetchResult = Invoke-Git" in script
    assert "$fetchResult = $script:launcherFetchResult" in script
    assert script.index("$fetchResult = $script:launcherFetchResult") < script.index(
        'Invoke-Git @("rev-list", "--count", "HEAD..@{u}")'
    )
