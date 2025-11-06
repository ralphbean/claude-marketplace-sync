# Claude Code Marketplace Aggregator

A tool for creating hierarchical Claude Code marketplaces through distributed composition. Each marketplace declares its immediate children, and through recursive application, creates arbitrarily deep marketplace hierarchies.

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [Usage](#usage)
- [CI/CD Integration](#cicd-integration)
- [Example Hierarchies](#example-hierarchies)
- [Provenance Tracking](#provenance-tracking)

## Overview

### The Problem

Claude Code marketplaces can only reference individual plugins, not other marketplaces. This makes it difficult to create organizational hierarchies like:

```
My Enterprise Marketplace
├── Engineering Department Marketplace
│   ├── The Platform Team Marketplace
│   │   ├── Pipeline Plugin
│   │   └── Build Plugin
│   └── API Helper Plugin
└── Operations Marketplace
    ├── Monitoring Plugin
    └── Incident Response Plugin
```

### The Solution

This tool enables **distributed marketplace composition**:

1. Each marketplace maintains a `.sync-config.json` declaring its immediate children
2. A script aggregates all plugins from child marketplaces
3. Denylisting allows curators to exclude specific plugins
4. Provenance metadata tracks where each plugin came from
5. When each level runs this tool, you get recursive composition

**Key insight:** Each marketplace only manages its direct children, but the recursive application creates an arbitrarily deep hierarchy.

## How It Works

### Distributed Recursion Example

**The Platform Team Marketplace** (leaf node):
```json
{
  "marketplace": {"name": "platform-team-marketplace"},
  "sources": [
    {
      "type": "skill",
      "name": "pipeline-debugger",
      "url": "https://github.com/the-platform-team/pipeline-debugger"
    }
  ]
}
```
Result: `platform-team-marketplace` contains 1 plugin

**Engineering Department Marketplace** (middle node):
```json
{
  "marketplace": {"name": "engineering-marketplace"},
  "sources": [
    {
      "type": "marketplace",
      "url": "https://github.com/the-platform-team/marketplace",
      "tag_prefix": "platform-team"
    },
    {
      "type": "skill",
      "name": "api-helper",
      "url": "https://github.com/engineering-department/api-helper"
    }
  ]
}
```
Result: `engineering-marketplace` contains 2 plugins (1 from Platform Team + 1 direct)

**My Enterprise Marketplace** (root node):
```json
{
  "marketplace": {"name": "enterprise-marketplace"},
  "sources": [
    {
      "type": "marketplace",
      "url": "https://github.com/engineering-department/marketplace",
      "tag_prefix": "engineering",
      "denylist": ["experimental-plugin"]
    },
    {
      "type": "marketplace",
      "url": "https://github.com/operations/marketplace",
      "tag_prefix": "operations"
    }
  ]
}
```
Result: `enterprise-marketplace` contains all plugins from both trees

### Provenance Tracking

Each plugin gets tagged with its source path:

```json
{
  "name": "pipeline-debugger",
  "source_marketplace": "enterprise/engineering/platform-team",
  ...
}
```

This allows users to:
- See where plugins originated
- Filter by source organization
- Understand trust boundaries

## Configuration

### Configuration File: `.sync-config.json`

```json
{
  "version": "1.0",
  "marketplace": {
    "name": "my-marketplace",
    "version": "1.0.0",
    "description": "My organization's Claude Code plugins",
    "owner": {
      "name": "My Org",
      "email": "plugins@myorg.com"
    }
  },
  "sources": [
    {
      "type": "marketplace",
      "url": "https://github.com/child-org/marketplace",
      "branch": "main",
      "denylist": ["unwanted-plugin"],
      "tag_prefix": "child-org"
    },
    {
      "type": "skill",
      "name": "my-custom-skill",
      "description": "A skill only in this marketplace",
      "url": "https://github.com/myorg/custom-skill",
      "branch": "main",
      "category": "development",
      "target_path": "skills/my-custom-skill"
    }
  ],
  "sync_settings": {
    "exclude_patterns": [".git", ".github", "node_modules"],
    "provenance_field": "source_marketplace"
  }
}
```

### Source Types

#### Marketplace Source

Pulls all plugins from a child marketplace:

```json
{
  "type": "marketplace",
  "url": "https://github.com/org/marketplace",
  "branch": "main",
  "denylist": ["plugin-to-exclude", "another-excluded"],
  "tag_prefix": "org-name"
}
```

- **url**: Git repository URL (GitHub, GitLab, or any git URL)
- **branch**: Branch to clone (default: "main")
- **denylist**: Array of plugin names to exclude
- **tag_prefix**: Prefix for provenance tracking

#### Skill Source

Adds a single skill directly:

```json
{
  "type": "skill",
  "name": "my-skill",
  "description": "Description of the skill",
  "url": "https://github.com/org/skill-repo",
  "branch": "main",
  "category": "development",
  "target_path": "skills/my-skill"
}
```

- **name**: Skill name (must be unique)
- **url**: Git repository URL for the skill
- **target_path**: Where to copy the skill in your marketplace
- **category**: Plugin category (optional)

### Sync Settings

```json
{
  "sync_settings": {
    "exclude_patterns": [".git", ".github", "node_modules", "__pycache__"],
    "provenance_field": "source_marketplace"
  }
}
```

- **exclude_patterns**: Files/directories to exclude when copying skills
- **provenance_field**: Field name for tracking plugin source (appears in marketplace.json)

## Usage

### Local Testing

```bash
# Run the sync script
python3 sync-marketplaces.py \
  --config .sync-config.json \
  --output .claude-plugin/marketplace.json \
  --verbose

# Check the generated marketplace
cat .claude-plugin/marketplace.json | jq '.plugins[] | {name, source_marketplace}'
```

### Command-Line Options

```
usage: sync-marketplaces.py [-h] [--config CONFIG] [--output OUTPUT] [-v]

optional arguments:
  -h, --help       show this help message and exit
  --config CONFIG  Path to sync configuration file (default: .sync-config.json)
  --output OUTPUT  Path to output marketplace.json file (default: .claude-plugin/marketplace.json)
  -v, --verbose    Enable verbose logging
```

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/sync-marketplaces.yml`:

```yaml
name: Sync Marketplaces

on:
  repository_dispatch:
    types: [marketplace-updated]
  schedule:
    - cron: '0 2 * * 1'  # Weekly on Monday 2 AM UTC
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Sync marketplaces
        run: python3 sync-marketplaces.py --verbose

      - name: Commit and push
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add .claude-plugin/marketplace.json
          git diff --staged --quiet || git commit -m "chore: sync marketplaces"
          git push
```

See [github/workflows/sync-marketplaces.yml](github/workflows/sync-marketplaces.yml) for a complete example.

### GitLab CI/CD

The GitLab CI/CD template is designed to be included and extended in your existing `.gitlab-ci.yml` file.

#### Basic Usage

Include the remote template and extend it to control when it runs:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/ralphbean/claude-marketplace-sync/main/gitlab/gitlab-ci.yml'

sync-marketplaces:
  extends: .sync-marketplaces-template
  only:
    - main  # Only run on main branch
```

#### Advanced Usage

Customize variables, add pre-processing steps, and control execution:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/ralphbean/claude-marketplace-sync/main/gitlab/gitlab-ci.yml'

sync-marketplaces:
  extends: .sync-marketplaces-template
  variables:
    SYNC_CONFIG: ".my-custom-config.json"
    OUTPUT_FILE: ".claude-plugin/my-marketplace.json"
    VERBOSE: "true"
  before_script:
    # Include the template's before_script commands
    - !reference [.sync-marketplaces-template, before_script]
    # Add your custom setup
    - echo "Running custom pre-sync validation"
    - ./scripts/validate-sources.sh
  only:
    - main
    - develop
```

#### Local Development

For testing in your repository before using the remote template:

```yaml
include:
  - local: 'gitlab/gitlab-ci.yml'

sync-marketplaces:
  extends: .sync-marketplaces-template
  only:
    - main
```

#### Customization Options

The template provides these configurable variables:

- **SYNC_CONFIG**: Path to sync configuration file (default: `.sync-config.json`)
- **OUTPUT_FILE**: Path to output marketplace.json (default: `.claude-plugin/marketplace.json`)
- **VERBOSE**: Enable verbose logging (default: `false`, set to `true` to enable)
- **GIT_DEPTH**: Git clone depth (default: `0` for full history)

The template runs by default on:
- Scheduled pipelines (configure in GitLab CI/CD > Schedules)
- Manual web triggers
- API/trigger token triggers

Override these with your own `only:`, `except:`, or `rules:` configuration.

See [gitlab/gitlab-ci.yml](gitlab/gitlab-ci.yml) for the full template source.

### Triggering Child Updates

When a child marketplace updates, trigger the parent's sync:

**GitHub (using repository dispatch):**
```bash
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/parent-org/marketplace/dispatches \
  -d '{"event_type":"marketplace-updated"}'
```

**GitLab (using trigger token):**
```bash
curl -X POST \
  -F token=$TRIGGER_TOKEN \
  -F ref=main \
  https://gitlab.com/api/v4/projects/PROJECT_ID/trigger/pipeline
```

## Example Hierarchies

### Example 1: Simple Two-Level Hierarchy

**Engineering Marketplace** (leaf):
```json
{
  "sources": [
    {"type": "skill", "name": "api-generator", "url": "..."},
    {"type": "skill", "name": "test-runner", "url": "..."}
  ]
}
```

**Company Marketplace** (root):
```json
{
  "sources": [
    {
      "type": "marketplace",
      "url": "https://github.com/company/engineering-marketplace",
      "tag_prefix": "engineering"
    }
  ]
}
```

Users can subscribe to:
- `company/engineering-marketplace` (2 plugins)
- `company/company-marketplace` (same 2 plugins, with provenance)

### Example 2: Enterprise Multi-Department Hierarchy

**Platform Team Marketplace**:
```json
{
  "sources": [
    {"type": "skill", "name": "pipeline-debugger", "url": "..."},
    {"type": "skill", "name": "build-analyzer", "url": "..."}
  ]
}
```

**Engineering Department Marketplace**:
```json
{
  "sources": [
    {
      "type": "marketplace",
      "url": "https://github.com/enterprise/platform-team-marketplace",
      "tag_prefix": "platform-team"
    },
    {"type": "skill", "name": "api-helper", "url": "..."}
  ]
}
```
Result: 3 plugins (2 from Platform Team + 1 direct)

**Operations Marketplace**:
```json
{
  "sources": [
    {"type": "skill", "name": "incident-response", "url": "..."},
    {"type": "skill", "name": "monitoring-setup", "url": "..."}
  ]
}
```
Result: 2 plugins

**My Enterprise Marketplace**:
```json
{
  "sources": [
    {
      "type": "marketplace",
      "url": "https://github.com/enterprise/engineering-marketplace",
      "tag_prefix": "engineering",
      "denylist": ["build-analyzer"]
    },
    {
      "type": "marketplace",
      "url": "https://github.com/enterprise/operations-marketplace",
      "tag_prefix": "operations"
    }
  ]
}
```
Result: 4 plugins (2 from engineering after denylist + 2 from operations)

Users can subscribe at any level:
- `enterprise/platform-team-marketplace` (2 plugins)
- `enterprise/engineering-marketplace` (3 plugins)
- `enterprise/operations-marketplace` (2 plugins)
- `enterprise/enterprise-marketplace` (4 plugins, all tagged with provenance)

### Example 3: Upstream + Downstream Pattern

**Public Marketplace** (upstream):
```json
{
  "sources": [
    {"type": "skill", "name": "public-tool-1", "url": "..."},
    {"type": "skill", "name": "public-tool-2", "url": "..."},
    {"type": "skill", "name": "experimental-alpha", "url": "..."}
  ]
}
```

**Internal Marketplace** (downstream):
```json
{
  "sources": [
    {
      "type": "marketplace",
      "url": "https://github.com/upstream/public-marketplace",
      "tag_prefix": "upstream",
      "denylist": ["experimental-alpha"]
    },
    {"type": "skill", "name": "internal-only-tool", "url": "..."}
  ]
}
```
Result: 3 plugins (2 from upstream + 1 internal)

## Provenance Tracking

Every plugin gets a `source_marketplace` field (configurable via `provenance_field`):

```json
{
  "name": "pipeline-debugger",
  "description": "Debug CI/CD pipelines",
  "version": "1.0.0",
  "source": "https://github.com/the-platform-team/pipeline-debugger",
  "category": "debugging",
  "source_marketplace": "enterprise/engineering/platform-team"
}
```

### Use Cases for Provenance

1. **Trust Decisions**: Users can see the chain of custody
2. **Filtering**: Filter plugins by organization
3. **Debugging**: Trace where a plugin came from
4. **Auditing**: Track which department/team owns which plugins

### Provenance Format

The provenance chain is built from `tag_prefix` values:

```
root_marketplace / child_marketplace / grandchild_marketplace
```

Example:
```
enterprise / engineering / platform-team
```

## Example Configurations

See the example configurations and CI/CD templates:

### Configuration Examples

- **[sync-config-simple.json](examples/sync-config-simple.json)** - Basic two-level hierarchy
- **[sync-config-enterprise.json](examples/sync-config-enterprise.json)** - Multi-department enterprise example
- **[sync-config-with-denylist.json](examples/sync-config-with-denylist.json)** - Curated marketplace with denylisting

### CI/CD Templates

- **[github/workflows/sync-marketplaces.yml](github/workflows/sync-marketplaces.yml)** - GitHub Actions workflow
- **[gitlab/gitlab-ci.yml](gitlab/gitlab-ci.yml)** - GitLab CI/CD template

## Workflow for Organizations

### Setting Up a Hierarchical Marketplace

1. **Leaf marketplaces** (individual teams/projects):
   - Create `.claude-plugin/marketplace.json` with their plugins
   - Optionally add `.sync-config.json` to aggregate from sub-teams
   - Set up CI/CD to rebuild on changes

2. **Middle marketplaces** (departments):
   - Create `.sync-config.json` referencing leaf marketplaces
   - Set up CI/CD to sync weekly + on repository_dispatch
   - Configure denylists for quality control

3. **Root marketplace** (organization):
   - Create `.sync-config.json` referencing department marketplaces
   - Set up CI/CD to sync on department updates
   - This becomes the "official" org marketplace

4. **Users**:
   - Can subscribe directly to their team's marketplace
   - OR subscribe to department/org marketplace for broader access
   - All plugins tagged with provenance for transparency

### Maintenance

Each team is responsible for:
- Their own plugins
- Their own `.sync-config.json`
- Triggering parent marketplace syncs when they update

This distributes maintenance burden and enables autonomous teams.

## Troubleshooting

### Script fails to clone repository

**Error**: `Failed to clone https://github.com/org/repo: ...`

**Solutions**:
- Ensure the repository URL is correct
- For private repos, configure git credentials or SSH keys
- Check that the branch exists

### Plugin not appearing in aggregated marketplace

**Possible causes**:
1. Plugin is in denylist - check `.sync-config.json`
2. Duplicate plugin name - first occurrence wins
3. Child marketplace hasn't been synced yet

### Provenance shows wrong path

**Check**:
- `tag_prefix` in source configuration
- Ensure parent marketplaces are using this script (not manually maintained)

## Contributing

Contributions welcome! This tool is designed to be:
- Platform-agnostic (GitHub, GitLab, any git)
- Flexible (skills and marketplaces)
- Transparent (provenance tracking)

If you find bugs or have feature requests, please open an issue.

## License

MIT
