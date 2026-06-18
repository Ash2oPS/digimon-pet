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
    assert 'if "!UPDATE_EXIT_CODE!"=="10"' in launcher
    assert 'call "%~f0" %*' in launcher


def test_windows_launcher_falls_back_to_origin_branch_without_upstream():
    script = (ROOT / "packaging" / "windows" / "launcher_update_check.ps1").read_text(encoding="utf-8")

    assert "Get-UpdateBranch" in script
    assert 'Invoke-Git @("rev-parse", "--abbrev-ref", "HEAD")' in script
    assert '"origin/$($currentBranch.Output.Trim())"' in script
    assert 'Invoke-Git @("rev-list", "--count", "HEAD..$($updateBranch.RemoteBranch)")' in script
    assert 'Invoke-Git @("pull", "--ff-only", "origin", $localBranch)' in script


def test_windows_vbs_runs_update_check_before_batch_launcher():
    launcher = (ROOT / "Digimon Pet.vbs").read_text(encoding="utf-8")

    update_check = 'fso.BuildPath(scriptDir, "packaging\\windows\\launcher_update_check.ps1")'
    batch_launcher = 'fso.BuildPath(scriptDir, "Digimon Pet.bat")'
    assert update_check in launcher
    assert 'DIGIMON_PET_UPDATE_CHECKED' in launcher
    assert launcher.index(update_check) < launcher.index(batch_launcher)


def test_windows_batch_bootstraps_python_without_stale_errorlevel_expansion():
    launcher = (ROOT / "Digimon Pet.bat").read_text(encoding="utf-8")

    assert "setlocal EnableExtensions EnableDelayedExpansion" in launcher
    assert "call :find_python" in launcher
    assert "call :try_python py -3.12" in launcher
    assert "call :try_python python" in launcher
    assert "winget install --id Python.Python.3.12" in launcher
    assert '"!PYTHON_EXE!" -m venv .venv' in launcher
    assert '"%PYTHON_EXE%" -m venv .venv' not in launcher
    assert "if %ERRORLEVEL% EQU 0" not in launcher
    assert "if %ERRORLEVEL% NEQ 0" not in launcher


def test_windows_batch_skips_missing_absolute_python_paths_before_execution():
    launcher = (ROOT / "Digimon Pet.bat").read_text(encoding="utf-8")
    try_python_block = launcher[launcher.rindex(":try_python") : launcher.rindex(":install_python")]

    assert 'if "%_PY_CMD%"=="%_PY_CMD:\\=%" (' in launcher
    assert ") else (" in try_python_block
    assert "exit /b 1" in try_python_block


def test_windows_batch_avoids_shell_redirection_chars_in_python_version_check():
    launcher = (ROOT / "Digimon Pet.bat").read_text(encoding="utf-8")
    try_python_block = launcher[launcher.rindex(":try_python") : launcher.rindex(":install_python")]

    assert "digimon_pet_python_probe_%RANDOM%.py" in try_python_block
    assert 'echo if sys.version_info[0] not in [3]: sys.exit^(1^)' in try_python_block
    assert 'echo print^(sys.executable^)' in try_python_block
    assert "!=" not in try_python_block
    assert ' -c "' not in try_python_block


def test_windows_batch_wraps_quoted_python_probe_commands_for_for_f():
    launcher = (ROOT / "Digimon Pet.bat").read_text(encoding="utf-8")
    try_python_block = launcher[launcher.rindex(":try_python") : launcher.rindex(":install_python")]

    assert "cmd /d /c" in try_python_block
    assert '"%_PY_CMD%" %_PY_ARG% "%_PY_PROBE%"' in try_python_block


def test_windows_batch_forces_winget_python_install_when_package_is_registered_but_missing():
    launcher = (ROOT / "Digimon Pet.bat").read_text(encoding="utf-8")
    missing_python_block = launcher[launcher.index("if not defined PYTHON_EXE (") : launcher.index('"!PYTHON_EXE!" -m venv .venv')]

    assert "winget install --id Python.Python.3.12" in launcher
    assert "call :install_python_force" in missing_python_block
    assert missing_python_block.index("call :install_python") < missing_python_block.index(
        "call :install_python_force"
    )
    assert "--force" in launcher[launcher.index(":install_python_force") :]


def test_windows_batch_has_repo_local_python_fallback_after_winget():
    launcher = (ROOT / "Digimon Pet.bat").read_text(encoding="utf-8")
    missing_python_block = launcher[launcher.index("if not defined PYTHON_EXE (") : launcher.index('"!PYTHON_EXE!" -m venv .venv')]
    find_python_block = launcher[launcher.rindex(":find_python") : launcher.rindex(":try_python")]

    assert 'set "LOCAL_PY=.local\\python312\\python.exe"' in launcher
    assert 'if exist "%LOCAL_PY%" (' in find_python_block
    assert find_python_block.index('if exist "%LOCAL_PY%" (') < find_python_block.index("call :try_python py -3.12")
    assert "call :install_python_local" in missing_python_block
    assert missing_python_block.index("call :install_python_force") < missing_python_block.index(
        "call :install_python_local"
    )
    assert "python.org/ftp/python/" in launcher
    assert "TargetDir=" in launcher
    assert "Include_pip=1" in launcher


def test_windows_batch_checks_absolute_python_launcher_after_install():
    launcher = (ROOT / "Digimon Pet.bat").read_text(encoding="utf-8")
    find_python_block = launcher[launcher.rindex(":find_python") : launcher.rindex(":try_python")]

    assert 'call :try_python "%LocalAppData%\\Programs\\Python\\Launcher\\py.exe" -3.12' in find_python_block
    assert 'call :try_python "%LocalAppData%\\Programs\\Python\\Launcher\\py.exe" -3.11' in find_python_block
    assert find_python_block.index('call :try_python "%LocalAppData%\\Programs\\Python\\Launcher\\py.exe" -3.12') < find_python_block.index(
        'call :try_python "%LocalAppData%\\Programs\\Python\\Python312\\python.exe"'
    )


def test_windows_local_python_install_ignores_stale_winget_errorlevel():
    launcher = (ROOT / "Digimon Pet.bat").read_text(encoding="utf-8")
    local_install_block = launcher[launcher.rindex(":install_python_local") :]

    assert 'if not exist ".local" (' in local_install_block
    assert 'mkdir ".local" || exit /b 1' in local_install_block
    assert 'if not exist ".local" mkdir ".local"\nif errorlevel 1 exit /b 1' not in local_install_block


def test_windows_launcher_stashes_local_changes_before_pull():
    script = (ROOT / "packaging" / "windows" / "launcher_update_check.ps1").read_text(encoding="utf-8")

    assert "Save-LocalChangesForUpdate" in script
    assert 'Invoke-Git @("status", "--porcelain")' in script
    assert 'Invoke-Git @("stash", "push", "-u", "-m", $stashMessage)' in script
    assert 'Invoke-Git @("stash", "pop")' in script
    assert script.index('Invoke-Git @("stash", "push", "-u", "-m", $stashMessage)') < script.index(
        'Invoke-Git @("pull", "--ff-only", "origin", $localBranch)'
    )
