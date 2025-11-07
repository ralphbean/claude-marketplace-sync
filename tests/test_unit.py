"""
Unit tests for MarketplaceAggregator class.

These tests mock git operations and test individual methods in isolation.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, mock_open
import pytest

# Import the class under test
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import with importlib since the module has a hyphen
import importlib.util

spec = importlib.util.spec_from_file_location(
    "sync_marketplaces", Path(__file__).parent.parent / "sync-marketplaces.py"
)
sync_marketplaces = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_marketplaces)
MarketplaceAggregator = sync_marketplaces.MarketplaceAggregator


class TestExtractRepoName:
    """Test _extract_repo_name method."""

    def test_extract_repo_name_https_url(self, tmp_path):
        """Test extracting repo name from HTTPS URL."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"sources": []}')

        aggregator = MarketplaceAggregator(str(config_file), "output.json")
        result = aggregator._extract_repo_name("https://github.com/owner/repo.git")
        assert result == "repo"

    def test_extract_repo_name_https_url_no_git(self, tmp_path):
        """Test extracting repo name from HTTPS URL without .git suffix."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"sources": []}')

        aggregator = MarketplaceAggregator(str(config_file), "output.json")
        result = aggregator._extract_repo_name("https://github.com/owner/repo")
        assert result == "repo"

    def test_extract_repo_name_ssh_url(self, tmp_path):
        """Test extracting repo name from SSH URL."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"sources": []}')

        aggregator = MarketplaceAggregator(str(config_file), "output.json")
        result = aggregator._extract_repo_name("git@github.com:owner/repo.git")
        assert result == "repo"

    def test_extract_repo_name_trailing_slash(self, tmp_path):
        """Test extracting repo name with trailing slash."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"sources": []}')

        aggregator = MarketplaceAggregator(str(config_file), "output.json")
        result = aggregator._extract_repo_name("https://github.com/owner/repo/")
        assert result == "repo"


class TestExtractVersionFromSkill:
    """Test _extract_version_from_skill method."""

    def test_extract_version_frontmatter(self, tmp_path):
        """Test extracting version from YAML frontmatter."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"sources": []}')

        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            """---
version: "2.1.5"
---

# My Skill
"""
        )

        aggregator = MarketplaceAggregator(str(config_file), "output.json")
        result = aggregator._extract_version_from_skill(skill_md)
        assert result == "2.1.5"

    def test_extract_version_frontmatter_no_quotes(self, tmp_path):
        """Test extracting version from YAML frontmatter without quotes."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"sources": []}')

        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            """---
version: 1.2.3
---

# My Skill
"""
        )

        aggregator = MarketplaceAggregator(str(config_file), "output.json")
        result = aggregator._extract_version_from_skill(skill_md)
        assert result == "1.2.3"

    def test_extract_version_metadata_section(self, tmp_path):
        """Test extracting version from metadata section."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"sources": []}')

        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            """# My Skill

## Skill Metadata

- version: "3.0.0"
- author: Test
"""
        )

        aggregator = MarketplaceAggregator(str(config_file), "output.json")
        result = aggregator._extract_version_from_skill(skill_md)
        assert result == "3.0.0"

    def test_extract_version_missing_file(self, tmp_path):
        """Test default version when SKILL.md is missing."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"sources": []}')

        skill_md = tmp_path / "SKILL.md"  # Don't create the file

        aggregator = MarketplaceAggregator(str(config_file), "output.json")
        result = aggregator._extract_version_from_skill(skill_md)
        assert result == "1.0.0"

    def test_extract_version_no_version(self, tmp_path):
        """Test default version when no version info in file."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"sources": []}')

        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("# My Skill\n\nNo version here!")

        aggregator = MarketplaceAggregator(str(config_file), "output.json")
        result = aggregator._extract_version_from_skill(skill_md)
        assert result == "1.0.0"


class TestConfigLoading:
    """Test configuration loading."""

    def test_load_basic_config(self, tmp_path):
        """Test loading a basic configuration."""
        config_file = tmp_path / "config.json"
        config_data = {
            "version": "1.0",
            "marketplace": {"name": "test-marketplace", "version": "1.0.0"},
            "sources": [],
        }
        config_file.write_text(json.dumps(config_data))

        aggregator = MarketplaceAggregator(str(config_file), "output.json")
        assert aggregator.config == config_data

    def test_load_config_with_sources(self, tmp_path):
        """Test loading configuration with sources."""
        config_file = tmp_path / "config.json"
        config_data = {
            "version": "1.0",
            "marketplace": {"name": "test-marketplace"},
            "sources": [
                {
                    "type": "marketplace",
                    "url": "https://example.com/repo",
                    "branch": "main",
                }
            ],
        }
        config_file.write_text(json.dumps(config_data))

        aggregator = MarketplaceAggregator(str(config_file), "output.json")
        assert len(aggregator.config["sources"]) == 1
        assert aggregator.config["sources"][0]["type"] == "marketplace"


class TestGenerateMarketplace:
    """Test _generate_marketplace method."""

    def test_generate_marketplace_basic(self, tmp_path):
        """Test generating a basic marketplace.json."""
        config_file = tmp_path / "config.json"
        config_data = {
            "marketplace": {
                "name": "test-marketplace",
                "version": "1.0.0",
                "description": "Test marketplace",
                "owner": {"name": "Test Owner", "email": "test@example.com"},
            },
            "sources": [],
        }
        config_file.write_text(json.dumps(config_data))

        output_file = tmp_path / "marketplace.json"
        aggregator = MarketplaceAggregator(str(config_file), str(output_file))

        # Add some test plugins
        aggregator.all_plugins = [
            {
                "name": "plugin1",
                "version": "1.0.0",
                "description": "Test plugin 1",
                "source": "./plugins/plugin1",
            },
            {
                "name": "plugin2",
                "version": "2.0.0",
                "description": "Test plugin 2",
                "source": "./plugins/plugin2",
            },
        ]

        aggregator._generate_marketplace()

        # Verify output file exists
        assert output_file.exists()

        # Verify content
        with open(output_file) as f:
            result = json.load(f)

        assert result["name"] == "test-marketplace"
        assert result["version"] == "1.0.0"
        assert len(result["plugins"]) == 2
        assert result["plugins"][0]["name"] == "plugin1"
        assert result["plugins"][1]["name"] == "plugin2"

    def test_generate_marketplace_deduplication(self, tmp_path):
        """Test that duplicate plugins are removed (keeping first)."""
        config_file = tmp_path / "config.json"
        config_data = {
            "marketplace": {"name": "test-marketplace", "version": "1.0.0"},
            "sources": [],
        }
        config_file.write_text(json.dumps(config_data))

        output_file = tmp_path / "marketplace.json"
        aggregator = MarketplaceAggregator(str(config_file), str(output_file))

        # Add duplicate plugins
        aggregator.all_plugins = [
            {
                "name": "plugin1",
                "version": "1.0.0",
            },
            {
                "name": "plugin2",
                "version": "2.0.0",
            },
            {
                "name": "plugin1",
                "version": "1.5.0",
            },  # Duplicate
        ]

        # Set origin_map
        aggregator.origin_map = {
            "plugin1": ["marketplace-a", "marketplace-b"],
            "plugin2": ["marketplace-a"],
        }

        aggregator._generate_marketplace()

        with open(output_file) as f:
            result = json.load(f)

        # Should only have 2 plugins (duplicate removed)
        assert len(result["plugins"]) == 2
        assert result["plugins"][0]["name"] == "plugin1"
        assert result["plugins"][0]["version"] == "1.0.0"  # First occurrence kept
        assert result["plugins"][1]["name"] == "plugin2"


class TestLogging:
    """Test logging functionality."""

    def test_log_verbose_mode(self, tmp_path, capsys):
        """Test that logging works in verbose mode."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"sources": []}')

        aggregator = MarketplaceAggregator(str(config_file), "output.json", verbose=True)
        aggregator.log("Test message")

        captured = capsys.readouterr()
        assert "INFO" in captured.out
        assert "Test message" in captured.out

    def test_log_non_verbose_mode(self, tmp_path, capsys):
        """Test that logging is suppressed in non-verbose mode."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"sources": []}')

        aggregator = MarketplaceAggregator(str(config_file), "output.json", verbose=False)
        aggregator.log("Test message")

        captured = capsys.readouterr()
        assert "Test message" not in captured.out

    def test_log_error_always_shown(self, tmp_path, capsys):
        """Test that error messages are always shown."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"sources": []}')

        aggregator = MarketplaceAggregator(str(config_file), "output.json", verbose=False)
        aggregator.log("Error message", level="error")

        captured = capsys.readouterr()
        assert "ERROR" in captured.err
        assert "Error message" in captured.err


class TestMarketplaceProcessing:
    """Test marketplace processing with mocked git operations."""

    @patch.object(MarketplaceAggregator, "_clone_repo")
    def test_process_marketplace_basic(self, mock_clone, tmp_path):
        """Test processing a marketplace with mocked git clone."""
        config_file = tmp_path / "config.json"
        config_data = {
            "marketplace": {"name": "test"},
            "sources": [],
        }
        config_file.write_text(json.dumps(config_data))

        # Create mock marketplace structure
        fake_marketplace_dir = tmp_path / "fake-marketplace"
        fake_marketplace_dir.mkdir()
        plugin_dir = fake_marketplace_dir / ".claude-plugin"
        plugin_dir.mkdir()

        marketplace_json = plugin_dir / "marketplace.json"
        marketplace_json.write_text(
            json.dumps(
                {
                    "plugins": [
                        {
                            "name": "test-plugin",
                            "version": "1.0.0",
                            "description": "Test",
                            "source": "./plugins/test-plugin",
                        }
                    ]
                }
            )
        )

        aggregator = MarketplaceAggregator(str(config_file), "output.json")

        # Mock clone to copy our fake marketplace
        def fake_clone(url, branch, target_dir):
            import shutil

            shutil.copytree(fake_marketplace_dir, target_dir, dirs_exist_ok=True)

        mock_clone.side_effect = fake_clone

        # Process the marketplace
        source = {
            "type": "marketplace",
            "url": "https://example.com/repo",
            "branch": "main",
            "denylist": [],
        }

        aggregator.temp_dir = tmp_path / "temp"
        aggregator.temp_dir.mkdir()
        aggregator._process_marketplace(source, parent_chain=[])

        # Verify plugin was added
        assert len(aggregator.all_plugins) == 1
        assert aggregator.all_plugins[0]["name"] == "test-plugin"
        # Verify origin is tracked
        assert "test-plugin" in aggregator.origin_map

    @patch.object(MarketplaceAggregator, "_clone_repo")
    def test_process_marketplace_with_denylist(self, mock_clone, tmp_path):
        """Test that denylisted plugins are skipped."""
        config_file = tmp_path / "config.json"
        config_data = {
            "marketplace": {"name": "test"},
            "sources": [],
        }
        config_file.write_text(json.dumps(config_data))

        # Create mock marketplace with multiple plugins
        fake_marketplace_dir = tmp_path / "fake-marketplace"
        fake_marketplace_dir.mkdir()
        plugin_dir = fake_marketplace_dir / ".claude-plugin"
        plugin_dir.mkdir()

        marketplace_json = plugin_dir / "marketplace.json"
        marketplace_json.write_text(
            json.dumps(
                {
                    "plugins": [
                        {"name": "allowed-plugin", "version": "1.0.0"},
                        {"name": "blocked-plugin", "version": "1.0.0"},
                        {"name": "another-allowed", "version": "1.0.0"},
                    ]
                }
            )
        )

        aggregator = MarketplaceAggregator(str(config_file), "output.json")

        def fake_clone(url, branch, target_dir):
            import shutil

            shutil.copytree(fake_marketplace_dir, target_dir, dirs_exist_ok=True)

        mock_clone.side_effect = fake_clone

        # Process with denylist
        source = {
            "type": "marketplace",
            "url": "https://example.com/repo",
            "branch": "main",
            "denylist": ["blocked-plugin"],
        }

        aggregator.temp_dir = tmp_path / "temp"
        aggregator.temp_dir.mkdir()
        aggregator._process_marketplace(source, parent_chain=[])

        # Verify only 2 plugins added (blocked one skipped)
        assert len(aggregator.all_plugins) == 2
        plugin_names = [p["name"] for p in aggregator.all_plugins]
        assert "allowed-plugin" in plugin_names
        assert "another-allowed" in plugin_names
        assert "blocked-plugin" not in plugin_names


class TestSourceURLConversion:
    """Test that local source paths are converted to remote URLs."""

    def test_marketplace_plugins_use_remote_source_urls(self, tmp_path):
        """Test that plugins from marketplaces have remote source URLs, not local paths."""
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "marketplace": {"name": "test", "version": "1.0.0"},
                    "sources": [],
                }
            )
        )

        aggregator = MarketplaceAggregator(str(config_file), str(tmp_path / "output.json"))
        aggregator.temp_dir = tmp_path / "temp"
        aggregator.temp_dir.mkdir()

        # Mock _clone_repo to create the marketplace structure
        def fake_clone(url, branch, target_dir):
            # Create marketplace directory structure
            target_dir.mkdir(parents=True, exist_ok=True)
            plugin_dir = target_dir / ".claude-plugin"
            plugin_dir.mkdir(parents=True, exist_ok=True)

            # Create marketplace.json with local source paths
            marketplace_json = plugin_dir / "marketplace.json"
            marketplace_json.write_text(
                json.dumps(
                    {
                        "plugins": [
                            {
                                "name": "test-plugin",
                                "description": "A test plugin",
                                "version": "1.0.0",
                                "source": "./plugins/test-plugin",  # Local path
                                "category": "test",
                            }
                        ]
                    }
                )
            )

        aggregator._clone_repo = fake_clone

        # Process the marketplace
        aggregator._process_marketplace(
            {
                "type": "marketplace",
                "url": "https://github.com/owner/upstream-marketplace",
                "branch": "main",
            },
            parent_chain=[],
        )

        # Verify the plugin was added with a remote URL source
        assert len(aggregator.all_plugins) == 1
        plugin = aggregator.all_plugins[0]
        assert plugin["name"] == "test-plugin"

        # Source should be a remote URL, not a local path
        assert not plugin["source"].startswith("./")
        assert plugin["source"].startswith("https://")
        assert "upstream-marketplace" in plugin["source"]
        assert "test-plugin" in plugin["source"]


class TestDiamondDependencyDeduplication:
    """Test that diamond dependencies are properly deduplicated with merged origin."""

    def test_diamond_dependency_merges_origin(self, tmp_path):
        """Test that when a plugin appears in multiple marketplaces, origin is merged into array."""
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "marketplace": {"name": "test", "version": "1.0.0"},
                    "sources": [],
                }
            )
        )

        aggregator = MarketplaceAggregator(str(config_file), str(tmp_path / "output.json"))
        aggregator.temp_dir = tmp_path / "temp"
        aggregator.temp_dir.mkdir()

        # Mock _clone_repo to create two different marketplaces with the same plugin
        call_count = [0]

        def fake_clone(url, branch, target_dir):
            call_count[0] += 1
            target_dir.mkdir(parents=True, exist_ok=True)
            plugin_dir = target_dir / ".claude-plugin"
            plugin_dir.mkdir(parents=True, exist_ok=True)

            # Both marketplaces have the same plugin
            marketplace_json = plugin_dir / "marketplace.json"
            marketplace_json.write_text(
                json.dumps(
                    {
                        "plugins": [
                            {
                                "name": "shared-plugin",
                                "description": "A plugin in both marketplaces",
                                "version": "1.0.0",
                                "source": "./plugins/shared-plugin",
                                "category": "test",
                            }
                        ]
                    }
                )
            )

        aggregator._clone_repo = fake_clone

        # Process two different marketplaces
        aggregator._process_marketplace(
            {
                "type": "marketplace",
                "url": "https://github.com/owner/marketplace-a",
                "branch": "main",
            },
            parent_chain=[],
        )
        aggregator._process_marketplace(
            {
                "type": "marketplace",
                "url": "https://github.com/owner/marketplace-b",
                "branch": "main",
            },
            parent_chain=[],
        )

        # Generate the final marketplace and origins
        aggregator._generate_marketplace()
        aggregator._generate_origins_file()

        # Read the generated file
        with open(aggregator.output_path) as f:
            result = json.load(f)

        # Should have exactly 1 plugin (deduplicated)
        assert len(result["plugins"]) == 1
        plugin = result["plugins"][0]
        assert plugin["name"] == "shared-plugin"

        # Verify origins.json was created with merged origins
        # origins.json should be in the same directory as marketplace.json
        origins_file = tmp_path / "origins.json"
        assert origins_file.exists()

        with open(origins_file) as f:
            origins = json.load(f)

        # origin should be an array with both sources, sorted for consistency
        assert isinstance(origins["shared-plugin"], list)
        assert len(origins["shared-plugin"]) == 2
        assert origins["shared-plugin"] == [
            "marketplace-a",
            "marketplace-b",
        ]  # Alphabetically sorted
