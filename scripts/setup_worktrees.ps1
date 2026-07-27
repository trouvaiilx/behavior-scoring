# PowerShell setup script to create isolated Git Worktrees for OpenCode instances (Phase 2)

Write-Host "Re-initializing Git Worktrees for Phase 2..." -ForegroundColor Green

# Remove stale worktrees if any
git worktree prune

# Create Phase 2 worktrees branching off API branch
git worktree add -b phase2/api-builder ..\behavior-scoring-builder API
git worktree add -b phase2/router-validator ..\behavior-scoring-validator API
git worktree add -b phase2/test-writer ..\behavior-scoring-tester API
git worktree add -b phase2/docs-integration ..\behavior-scoring-docs API

Write-Host "`nAll Phase 2 worktrees created successfully from API branch!" -ForegroundColor Green
Write-Host "You can now start OpenCode in each directory:" -ForegroundColor Yellow
Write-Host "  Terminal 1: cd ..\behavior-scoring-builder ; opencode"
Write-Host "  Terminal 2: cd ..\behavior-scoring-validator ; opencode"
Write-Host "  Terminal 3: cd ..\behavior-scoring-tester ; opencode"
Write-Host "  Terminal 4: cd ..\behavior-scoring-docs ; opencode"
