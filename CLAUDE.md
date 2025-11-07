# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Code Marketplace Aggregator enables distributed, hierarchical composition of Claude Code marketplaces. The tool recursively syncs plugins from multiple child marketplaces into a parent marketplace, supporting denylisting and origin tracking.

**Core concept:** Each marketplace only manages its immediate children (declared in `.sync-config.json`), but through recursive application across multiple levels, this creates arbitrarily deep marketplace hierarchies.

## Development Commands

### Pre-Commit Workflow

**IMPORTANT:** Always run `make` before committing changes. This runs linting and all tests to ensure code quality.

```bash
# Run linting and all tests (do this before committing!)
make
```

### Testing
```bash
# Run all tests (unit + functional)
make test

# Run only unit tests (fast, mocked git operations)
pytest tests/test_unit.py -v

# Run only functional tests (slower, real git operations)
pytest tests/test_functional.py -v

# Run a single test
pytest tests/test_unit.py::TestExtractRepoName::test_extract_repo_name_https_url -v
```

### Linting and Formatting
```bash
# Check code formatting (pre-commit check)
make lint
# Equivalent: black --check --line-length 100 .

# Fix formatting issues automatically
make format
# Equivalent: black --line-length 100 .
# Note: If linting fails, run this to auto-fix formatting issues
```

### Running the Script Locally
```bash
# Basic usage
python3 sync-marketplaces.py --config .sync-config.json --output .claude-plugin/marketplace.json

# With verbose logging
python3 sync-marketplaces.py --config examples/test-sync-config.json --verbose
```

### Cleanup
```bash
make clean  # Remove test artifacts and Python cache files
```

## Code Architecture

### Main Class: MarketplaceAggregator

Located in `sync-marketplaces.py:25-347`, this class orchestrates the entire sync process:

1. **Initialization** (`__init__`): Loads config, initializes tracking structures
2. **Main Entry** (`run`): Creates temp directory, processes sources, generates outputs
3. **Source Processing** (`_process_source`): Routes to marketplace or skill processing
4. **Output Generation**: Creates `marketplace.json` and `origins.json` files

### Key Data Structures

**`self.all_plugins`** (List[Dict]): Accumulates all plugin entries from all sources
- Duplicates are intentionally kept during processing
- Deduplication happens in `_generate_marketplace()` (keeps first occurrence)

**`self.origin_map`** (Dict[str, List[str]]): Tracks plugin provenance
- Maps plugin name → list of origin chains (e.g., `["enterprise/engineering/platform-team"]`)
- Diamond dependencies result in multiple origins
- Written to separate `origins.json` file (not in `marketplace.json` to maintain schema compliance)

### Processing Flow

1. **Marketplace Sources** (`_process_marketplace`):
   - Clones child marketplace repository
   - Reads its `marketplace.json`
   - Adds plugins (with denylist filtering)
   - Converts local source paths (`./plugins/foo`) to remote URLs
   - Non-recursive: only processes immediate children

2. **Skill Sources** (`_process_skill`):
   - Clones skill repository
   - Copies files to target location (respecting `exclude_patterns`)
   - Extracts version from `SKILL.md` (YAML frontmatter or metadata section)
   - Creates plugin entry with local source path

3. **Origin Tracking**:
   - Each marketplace source adds its `tag_prefix` to the parent chain
   - Skills use "direct" if no parent chain
   - Diamond dependencies merge origins into arrays in `origins.json`

### Important Implementation Details

**Deduplication Strategy** (sync-marketplaces.py:279-292):
- First occurrence of plugin name wins
- Duplicate entries are logged but discarded
- Origin tracking merges all sources for the plugin

**Source URL Conversion** (sync-marketplaces.py:131-135):
- Local paths like `./skills/foo` are converted to GitHub tree URLs
- Format: `{repo_url}/tree/{branch}/{local_path}`
- Ensures plugins reference upstream sources, not local checkouts

**Version Extraction** (sync-marketplaces.py:245-273):
- Tries YAML frontmatter: `version: "1.0.0"`
- Falls back to metadata section: `## Skill Metadata\n- version: "1.0.0"`
- Defaults to "1.0.0" if not found

**Git Operations** (sync-marketplaces.py:202-231):
- Uses shallow clones (`--depth 1`) for efficiency
- Disables credential prompts to prevent hanging on invalid URLs
- Environment variables: `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS=true`

## Testing Strategy

### Unit Tests (tests/test_unit.py)
- Mock git operations with `@patch` decorators
- Test individual methods in isolation
- Fast execution, no network dependencies
- Focus on edge cases and error handling

### Functional Tests (tests/test_functional.py)
- Real git clone operations (using `ralphbean/claude-code-plugins` as test fixture)
- End-to-end workflow validation
- Tests actual network operations and file I/O
- Slower but provides confidence in real-world scenarios

**Important Test Pattern**: Tests use `importlib.util` to import `sync-marketplaces.py` because the filename contains a hyphen.

## GitHub Action Integration

This repository provides a reusable GitHub Action defined in `action.yml`:

**Usage in other repos:**
```yaml
- uses: ralphbean/claude-marketplace-sync@main
  with:
    config-path: '.sync-config.json'
    verbose: 'true'
```

**Outputs:** `plugins-count`, `marketplaces-processed` (parsed from script output)

## Configuration Schema

See `.sync-config.json` structure:

- **marketplace**: Metadata for generated marketplace
- **sources**: Array of marketplace or skill sources
  - **type**: "marketplace" or "skill"
  - **url**: Git repository URL
  - **branch**: Branch to clone (default: "main")
  - **denylist**: Array of plugin names to exclude (marketplace sources only)
  - **tag_prefix**: Origin tracking label (marketplace sources only)
- **sync_settings.exclude_patterns**: Files/directories to skip when copying skills

## Origin Tracking Architecture

Origin metadata is kept in a **separate file** (`.claude-plugin/origins.json`), not embedded in `marketplace.json`, to maintain compliance with Claude Code's marketplace schema.

**Format:**
```json
{
  "single-source-plugin": "enterprise/engineering",
  "multi-source-plugin": ["source-a", "source-b"]  // Diamond dependency
}
```

**Rationale:** Claude Code's official schema doesn't include `source_marketplace` field, so origin tracking is maintained separately.
