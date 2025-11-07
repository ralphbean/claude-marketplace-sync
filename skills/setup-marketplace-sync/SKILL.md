# Setup Marketplace Sync

## Skill Metadata
- version: "1.2.0"
- description: "Configure automated Claude Code marketplace synchronization in your repository"
- author: "Claude Code Marketplace Aggregator"

## Overview

This skill helps you set up automated synchronization of Claude Code plugins from multiple marketplaces into your own aggregated marketplace. It handles both GitHub Actions and GitLab CI/CD pipelines, including automated scheduling setup.

## Instructions for Claude Code

When this skill is invoked, follow these steps carefully:

### Step 1: Gather User Requirements

Use the `AskUserQuestion` tool to collect the following information:

1. **Platform**: Ask whether the user is using GitHub or GitLab
   - Options: "GitHub", "GitLab"

2. **Marketplaces to sync**: Ask for a list of marketplace repositories to sync from
   - Explain: "Enter the Git URLs of marketplaces you want to sync plugins from (e.g., https://github.com/org/marketplace-repo)"
   - Allow multiple entries
   - For each marketplace, ask:
     - Repository URL (required)
     - Branch name (default: "main")
     - Tag prefix for origin tracking (e.g., "enterprise/engineering")
     - Any plugins to denylist (comma-separated names)

3. **Local skills**: Ask if they want to include any local skill directories
   - If yes, collect:
     - Skill directory path (relative to repo root)
     - Skill name
     - Skill description

4. **For GitLab only**:
   - GitLab runner tags (REQUIRED) - Ask: "What GitLab runner tags should be used? (e.g., 'docker', 'linux', 'shared'). If unsure, check your GitLab project's Settings → CI/CD → Runners to see available tags."
   - GitLab server URL (default: "https://gitlab.com")
   - Project ID or namespace/project-name
   - GitLab access token (PAT) - explain it needs `api` scope
   - Schedule preference (default: "0 2 * * *" - 2 AM daily)

### Step 2: Search for Existing Configuration

Use the `Glob` tool to search for existing sync configuration:

```
pattern: "**/.sync-config.json"
```

If found:
- Read the file using the `Read` tool
- Ask user: "Found existing .sync-config.json at {path}. Would you like to update it or create a new one?"
- If update: merge new sources with existing ones (avoid duplicates)

If not found:
- Proceed to create new configuration

### Step 3: Create or Update .sync-config.json

Create the configuration file at the repository root with this structure:

```json
{
  "marketplace": {
    "name": "My Aggregated Marketplace",
    "description": "Aggregated Claude Code plugins from multiple sources",
    "author": "Your Organization",
    "homepage": "https://github.com/your-org/your-repo"
  },
  "sources": [
    {
      "type": "marketplace",
      "url": "https://github.com/source-org/source-marketplace",
      "branch": "main",
      "tag_prefix": "source-name",
      "denylist": []
    }
  ],
  "sync_settings": {
    "exclude_patterns": [
      ".git",
      "*.pyc",
      "__pycache__",
      ".pytest_cache"
    ]
  }
}
```

**Important**:
- Populate `marketplace` metadata with sensible defaults or user-provided values
- Add each marketplace source from user input to the `sources` array
- For local skills, add entries with `"type": "skill"` and the local path
- Ensure JSON is valid and properly formatted

### Step 4: Set Up CI/CD Pipeline

#### For GitHub:

1. Create `.github/workflows/sync-marketplace.yml`:

```yaml
name: Sync Marketplace

on:
  schedule:
    # Run daily at 2 AM UTC
    - cron: '0 2 * * *'
  workflow_dispatch: # Allow manual triggering

permissions:
  contents: write

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: ralphbean/claude-marketplace-sync@main
        with:
          config-path: '.sync-config.json'
          verbose: 'true'

      - name: Commit and push changes
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

          if [[ -n $(git status --porcelain) ]]; then
            git add .claude-plugin/
            git commit -m "chore: sync marketplace plugins

            🤖 Automated sync from configured marketplace sources"
            git push
          else
            echo "No changes to commit"
          fi
```

2. Inform the user:
   - "✓ Created GitHub Actions workflow at .github/workflows/sync-marketplace.yml"
   - "The workflow will run daily at 2 AM UTC and can be triggered manually"
   - "No additional setup needed - GitHub Actions is ready to go!"

#### For GitLab:

1. Create `.gitlab-ci.yml`:

```yaml
# Include the reusable sync template from the marketplace-sync repository
include:
  - remote: 'https://raw.githubusercontent.com/ralphbean/claude-marketplace-sync/main/.gitlab-ci-template.yml'

# Configure sync behavior (optional - these are the defaults)
variables:
  SYNC_CONFIG_PATH: ".sync-config.json"
  SYNC_OUTPUT_PATH: ".claude-plugin/marketplace.json"
  SYNC_VERBOSE: "true"

# Specify your GitLab runner tags (REQUIRED)
sync-marketplace:
  tags:
    - <REPLACE_WITH_USER_PROVIDED_TAGS>
```

**Important**: Replace `<REPLACE_WITH_USER_PROVIDED_TAGS>` with the actual tags provided by the user. If the user provided multiple tags (comma-separated), create a list entry for each tag. For example, if user provided "docker,linux", generate:

```yaml
sync-marketplace:
  tags:
    - docker
    - linux
```

2. **Attempt automated setup via GitLab API**:

   Use the `Bash` tool to attempt the following:

   a. **Set CI/CD variable for GITLAB_TOKEN**:
   ```bash
   curl --request POST \
     --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
     "${GITLAB_URL}/api/v4/projects/${PROJECT_ID}/variables" \
     --form "key=GITLAB_TOKEN" \
     --form "value=${GITLAB_TOKEN}" \
     --form "protected=false" \
     --form "masked=true"
   ```

   b. **Create pipeline schedule**:
   ```bash
   curl --request POST \
     --header "PRIVATE-TOKEN: ${GITLAB_TOKEN}" \
     "${GITLAB_URL}/api/v4/projects/${PROJECT_ID}/pipeline_schedules" \
     --form "description=Daily marketplace sync" \
     --form "ref=main" \
     --form "cron=0 2 * * *" \
     --form "cron_timezone=UTC" \
     --form "active=true"
   ```

3. **Handle API results**:

   - If successful (HTTP 200/201): Inform user that setup is complete
   - If failed (HTTP 401/403 - insufficient permissions): Provide manual instructions below
   - If failed (other error): Show error and provide manual instructions

4. **Manual setup instructions** (provide if API fails):

```
⚠️  Automated setup failed. Please complete these steps manually:

1. Set up GitLab CI/CD Variable:
   - Go to: Settings → CI/CD → Variables
   - Click "Add variable"
   - Key: GITLAB_TOKEN
   - Value: [your GitLab PAT with 'api' and 'write_repository' scopes]
   - Flags: Check "Mask variable"
   - Click "Add variable"

2. Create Pipeline Schedule:
   - Go to: CI/CD → Schedules
   - Click "New schedule"
   - Description: "Daily marketplace sync"
   - Interval Pattern: Custom (0 2 * * *)
   - Cron timezone: UTC
   - Target branch: main
   - Click "Save pipeline schedule"

3. Token Requirements:
   Your GitLab Personal Access Token needs these scopes:
   - ✓ api (full API access)
   - ✓ write_repository (push changes)

   To create a token:
   - Go to: User Settings → Access Tokens
   - Name: "Marketplace Sync"
   - Expiration: Set as needed
   - Select scopes: api, write_repository
   - Click "Create personal access token"
   - Copy the token (you won't see it again!)

4. Test the Pipeline:
   - Go to: CI/CD → Schedules
   - Click the play button (▶) next to your schedule
   - Monitor: CI/CD → Pipelines
```

### Step 5: Create README Documentation

Create or update a `MARKETPLACE-SYNC.md` file with:
- Overview of the sync setup
- List of configured marketplace sources
- How to manually trigger sync (GitHub: Actions tab, GitLab: Schedules)
- How to add new marketplace sources (edit .sync-config.json)
- How to denylist plugins (add to denylist array)

### Step 6: Final Summary

Provide a concise summary:

```
✅ Marketplace sync setup complete!

Configuration:
- Platform: [GitHub/GitLab]
- Marketplaces: [count] configured
- Local skills: [count] included
- Schedule: Daily at 2 AM UTC

Next steps:
1. Review .sync-config.json to verify sources
2. [For GitLab] Complete manual setup steps above if needed
3. Commit these changes to your repository
4. [Platform-specific] The first sync will run on schedule or can be triggered manually

Files created/updated:
- .sync-config.json
- [.github/workflows/sync-marketplace.yml OR .gitlab-ci.yml]
- MARKETPLACE-SYNC.md

The sync will generate:
- .claude-plugin/marketplace.json (aggregated marketplace)
- .claude-plugin/origins.json (plugin origin tracking)
```

## Error Handling

- If any git commands fail, provide clear error messages
- If API calls fail, always fall back to manual instructions
- If configuration file is malformed, validate and fix JSON syntax
- If paths don't exist, create necessary directories
- Always verify token permissions before attempting automated setup

## Testing Recommendations

After setup, suggest the user:
1. Manually trigger the pipeline to test it works
2. Verify .claude-plugin/marketplace.json is generated correctly
3. Check that origins.json tracks sources properly
4. Review pipeline logs for any warnings

## Notes

- This skill does NOT commit changes automatically - let the user review first
- For GitLab, token security is critical - always mask the variable
- The sync runs in a clone of the repo, so local paths in config must be relative
- Diamond dependencies (same plugin from multiple sources) are handled automatically
