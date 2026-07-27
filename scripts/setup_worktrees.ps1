# PowerShell setup script to create isolated Git Worktrees for OpenCode instances

Write-Host "Creating Git Worktrees for OpenCode Multi-Agent execution..." -ForegroundColor Green

# Ensure main directory is clean or committed first
git worktree add -b feature/api-builder ..\behavior-scoring-builder
git worktree add -b feature/router-validator ..\behavior-scoring-validator
git worktree add -b feature/test-writer ..\behavior-scoring-tester
git worktree add -b feature/docs-integration ..\behavior-scoring-docs

Write-Host "`nAll worktrees created successfully!" -ForegroundColor Green
Write-Host "You can now open 4 terminal tabs and cd into each directory to start OpenCode:" -ForegroundColor Yellow
Write-Host "  Terminal 1: cd ..\behavior-scoring-builder ; opencode"
Write-Host "  Terminal 2: cd ..\behavior-scoring-validator ; opencode"
Write-Host "  Terminal 3: cd ..\behavior-scoring-tester ; opencode"
Write-Host "  Terminal 4: cd ..\behavior-scoring-docs ; opencode"
Write-Host "All features will merge back into the 'API' branch." -ForegroundColor Cyan
