# Fetch github --prune, then for each worktree print one line.
# Clean and behind: fast-forward to github/<branch>.
# Clean and ahead (including a branch github does not have yet): push and
# set upstream to github/<branch>. A normal push only; never a force-push.
# Dirty or diverged: print the line and leave the worktree alone.
# --dry-run fetches and prints the same lines. It does not pull or push.
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$DryRun = $false
foreach ($arg in $args) {
    if ($arg -eq "--dry-run") {
        $DryRun = $true
    } else {
        [Console]::Error.WriteLine("unknown arg: $arg")
        exit 2
    }
}

$env:GIT_TERMINAL_PROMPT = "0"
$env:GIT_MERGE_AUTOEDIT = "no"

$null = git rev-parse --show-toplevel 2>$null
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine("not a git repository")
    exit 1
}
Set-Location ((git rev-parse --show-toplevel).Trim())

$null = git remote get-url github 2>$null
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine("github remote is not configured")
    exit 1
}

git fetch github --prune *>$null
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine("fetch github failed")
    exit 1
}

function Test-Ancestor {
    param([string]$Older, [string]$Newer)
    git merge-base --is-ancestor $Older $Newer *>$null
    return ($LASTEXITCODE -eq 0)
}

$entries = New-Object System.Collections.Generic.List[object]
$current = $null
foreach ($line in @(git worktree list --porcelain)) {
    if ($line.StartsWith("worktree ")) {
        if ($null -ne $current) { $entries.Add($current) }
        $current = [pscustomobject]@{ path = $line.Substring(9); head = ""; kind = ""; branch = "" }
    } elseif ($null -eq $current) {
        continue
    } elseif ($line.StartsWith("HEAD ")) {
        $current.head = $line.Substring(5).Trim()
    } elseif ($line.StartsWith("branch ")) {
        $current.kind = "branch"
        $prefix = "branch refs/heads/"
        $current.branch = $line.Substring($prefix.Length)
    } elseif ($line -eq "detached") {
        $current.kind = "detached"
    }
}
if ($null -ne $current) { $entries.Add($current) }

foreach ($entry in $entries) {
    $path = $entry.path
    $head = $entry.head
    $branch = $entry.branch
    if ($entry.kind -ne "branch" -or [string]::IsNullOrWhiteSpace($branch)) {
        $label = "detached"
        if (-not [string]::IsNullOrWhiteSpace($head)) {
            $short = $head.Substring(0, [Math]::Min(7, $head.Length))
            $label = "detached $short"
        }
        Write-Output "($label): left untouched"
        continue
    }

    $dirty = @(git -C $path status --porcelain)
    $remoteRef = "github/$branch"
    $relation = "ahead"
    $remote = git rev-parse --verify --quiet $remoteRef 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($remote)) {
        $remote = $remote.Trim()
        if ($head -eq $remote) {
            $relation = "same"
        } elseif (Test-Ancestor -Older $head -Newer $remote) {
            $relation = "behind"
        } elseif (Test-Ancestor -Older $remote -Newer $head) {
            $relation = "ahead"
        } else {
            $relation = "diverged"
        }
    }

    if ($dirty.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($dirty[0])) {
        Write-Output "${branch}: dirty, left untouched"
    } elseif ($relation -eq "same") {
        Write-Output "${branch}: up to date"
    } elseif ($relation -eq "diverged") {
        Write-Output "${branch}: diverged, left untouched"
    } elseif ($relation -eq "behind") {
        if ($DryRun) {
            Write-Output "${branch}: behind, would fast-forward"
        } else {
            git -C $path merge --ff-only --quiet -- $remoteRef *>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Output "${branch}: behind, fast-forwarded"
            } else {
                Write-Output "${branch}: behind, fast-forward failed, left untouched"
            }
        }
    } elseif ($DryRun) {
        Write-Output "${branch}: ahead, would push"
    } else {
        git -C $path push --quiet -u github -- $branch *>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Output "${branch}: ahead, pushed"
        } else {
            Write-Output "${branch}: ahead, push refused, left untouched"
        }
    }
}
