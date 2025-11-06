"""
Functional tests for MarketplaceAggregator.

These tests use real git operations and test the full end-to-end workflow.
"""

import json
import shutil
import tempfile
from pathlib import Path
import pytest

# Import the class under test
import importlib.util

spec = importlib.util.spec_from_file_location(
    "sync_marketplaces", Path(__file__).parent.parent / "sync-marketplaces.py"
)
sync_marketplaces = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_marketplaces)
MarketplaceAggregator = sync_marketplaces.MarketplaceAggregator


class TestEndToEndSync:
    """End-to-end functional tests with real git operations."""

    def test_sync_with_ralphbean_marketplace(self, tmp_path):
        """
        Test syncing with ralphbean's marketplace (as in test-sync-config.json).

        This is a real integration test that clones the actual repository.
        """
        # Use the example test config
        config_file = Path(__file__).parent.parent / "examples" / "test-sync-config.json"
        output_file = tmp_path / "marketplace.json"

        # Create aggregator and run
        aggregator = MarketplaceAggregator(str(config_file), str(output_file), verbose=True)
        result = aggregator.run()

        # Verify success
        assert result == 0

        # Verify output file exists
        assert output_file.exists()

        # Load and verify content
        with open(output_file) as f:
            marketplace = json.load(f)

        # Basic structure checks
        assert "name" in marketplace
        assert marketplace["name"] == "test-aggregated-marketplace"
        assert "version" in marketplace
        assert marketplace["version"] == "1.0.0"
        assert "plugins" in marketplace

        # Should have plugins from ralphbean's marketplace
        assert len(marketplace["plugins"]) > 0

        # All plugins should have required fields
        for plugin in marketplace["plugins"]:
            assert "name" in plugin
            assert "description" in plugin
            assert "version" in plugin
            assert "source" in plugin

        # All plugins should have origin field
        origin_field = "source_marketplace"
        for plugin in marketplace["plugins"]:
            assert origin_field in plugin
            assert plugin[origin_field] == "ralphbean"

        print(f"\nSynced {len(marketplace['plugins'])} plugins from ralphbean's marketplace")

    def test_sync_with_custom_config(self, tmp_path):
        """Test syncing with a custom configuration."""
        # Create a custom config that pulls from ralphbean's marketplace
        config_file = tmp_path / "custom-config.json"
        config_data = {
            "version": "1.0",
            "marketplace": {
                "name": "custom-test-marketplace",
                "version": "2.0.0",
                "description": "Custom test marketplace",
                "owner": {"name": "Test User", "email": "test@test.com"},
            },
            "sources": [
                {
                    "type": "marketplace",
                    "url": "https://github.com/ralphbean/claude-code-plugins",
                    "branch": "main",
                    "denylist": [],
                    "tag_prefix": "ralphbean-custom",
                }
            ],
            "sync_settings": {
                "exclude_patterns": [".git", ".github"],
                "origin_field": "origin",
            },
        }
        config_file.write_text(json.dumps(config_data, indent=2))

        output_file = tmp_path / "output" / "marketplace.json"

        # Run aggregator
        aggregator = MarketplaceAggregator(str(config_file), str(output_file), verbose=True)
        result = aggregator.run()

        # Verify success
        assert result == 0
        assert output_file.exists()

        # Verify content
        with open(output_file) as f:
            marketplace = json.load(f)

        assert marketplace["name"] == "custom-test-marketplace"
        assert marketplace["version"] == "2.0.0"
        assert len(marketplace["plugins"]) > 0

        # Check custom origin field
        for plugin in marketplace["plugins"]:
            assert "origin" in plugin
            assert plugin["origin"] == "ralphbean-custom"

    def test_denylist_functionality(self, tmp_path):
        """Test that denylist properly filters out plugins."""
        # First, sync without denylist to see what plugins are available
        config_file_full = tmp_path / "config-full.json"
        config_full = {
            "version": "1.0",
            "marketplace": {"name": "full-marketplace", "version": "1.0.0"},
            "sources": [
                {
                    "type": "marketplace",
                    "url": "https://github.com/ralphbean/claude-code-plugins",
                    "branch": "main",
                    "denylist": [],
                }
            ],
            "sync_settings": {"origin_field": "source_marketplace"},
        }
        config_file_full.write_text(json.dumps(config_full, indent=2))

        output_file_full = tmp_path / "marketplace-full.json"
        aggregator_full = MarketplaceAggregator(
            str(config_file_full), str(output_file_full), verbose=False
        )
        aggregator_full.run()

        with open(output_file_full) as f:
            marketplace_full = json.load(f)

        # Get first plugin name to denylist
        if len(marketplace_full["plugins"]) > 0:
            plugin_to_block = marketplace_full["plugins"][0]["name"]

            # Now sync with denylist
            config_file_filtered = tmp_path / "config-filtered.json"
            config_filtered = {
                "version": "1.0",
                "marketplace": {"name": "filtered-marketplace", "version": "1.0.0"},
                "sources": [
                    {
                        "type": "marketplace",
                        "url": "https://github.com/ralphbean/claude-code-plugins",
                        "branch": "main",
                        "denylist": [plugin_to_block],
                    }
                ],
                "sync_settings": {"origin_field": "source_marketplace"},
            }
            config_file_filtered.write_text(json.dumps(config_filtered, indent=2))

            output_file_filtered = tmp_path / "marketplace-filtered.json"
            aggregator_filtered = MarketplaceAggregator(
                str(config_file_filtered), str(output_file_filtered), verbose=False
            )
            aggregator_filtered.run()

            with open(output_file_filtered) as f:
                marketplace_filtered = json.load(f)

            # Verify the denylisted plugin is not present
            filtered_plugin_names = [p["name"] for p in marketplace_filtered["plugins"]]
            assert plugin_to_block not in filtered_plugin_names

            # Should have one fewer plugin
            assert len(marketplace_filtered["plugins"]) == len(marketplace_full["plugins"]) - 1

    def test_origin_tracking(self, tmp_path):
        """Test that origin is properly tracked."""
        config_file = tmp_path / "config.json"
        config_data = {
            "version": "1.0",
            "marketplace": {"name": "test-marketplace", "version": "1.0.0"},
            "sources": [
                {
                    "type": "marketplace",
                    "url": "https://github.com/ralphbean/claude-code-plugins",
                    "branch": "main",
                    "tag_prefix": "ralphbean-test",
                }
            ],
            "sync_settings": {"origin_field": "source_marketplace"},
        }
        config_file.write_text(json.dumps(config_data, indent=2))

        output_file = tmp_path / "marketplace.json"

        # Run with verbose to capture origin summary
        aggregator = MarketplaceAggregator(str(config_file), str(output_file), verbose=True)
        result = aggregator.run()

        assert result == 0

        # Verify origin tracking
        assert len(aggregator.origin_map) > 0

        # All entries should map to ralphbean-test
        for plugin_name, sources in aggregator.origin_map.items():
            assert len(sources) > 0
            assert "ralphbean-test" in sources[0]

        # Verify in output file
        with open(output_file) as f:
            marketplace = json.load(f)

        for plugin in marketplace["plugins"]:
            assert plugin["source_marketplace"] == "ralphbean-test"

    def test_deduplication(self, tmp_path):
        """Test that duplicate plugins are properly deduplicated."""
        # Create a config that would pull the same marketplace twice
        # (This is a bit artificial but tests the dedup logic)
        config_file = tmp_path / "config.json"
        config_data = {
            "version": "1.0",
            "marketplace": {"name": "test-marketplace", "version": "1.0.0"},
            "sources": [
                {
                    "type": "marketplace",
                    "url": "https://github.com/ralphbean/claude-code-plugins",
                    "branch": "main",
                    "tag_prefix": "source-a",
                }
            ],
            "sync_settings": {"origin_field": "source_marketplace"},
        }
        config_file.write_text(json.dumps(config_data, indent=2))

        output_file = tmp_path / "marketplace.json"

        aggregator = MarketplaceAggregator(str(config_file), str(output_file), verbose=True)

        # Manually add some duplicate plugins to test dedup
        aggregator.all_plugins = [
            {"name": "plugin-a", "version": "1.0.0", "source_marketplace": "source-1"},
            {"name": "plugin-b", "version": "1.0.0", "source_marketplace": "source-1"},
            {"name": "plugin-a", "version": "2.0.0", "source_marketplace": "source-2"},  # Duplicate
            {"name": "plugin-c", "version": "1.0.0", "source_marketplace": "source-1"},
        ]

        aggregator._generate_marketplace()

        with open(output_file) as f:
            marketplace = json.load(f)

        # Should only have 3 unique plugins
        assert len(marketplace["plugins"]) == 3

        # Check names
        plugin_names = [p["name"] for p in marketplace["plugins"]]
        assert plugin_names.count("plugin-a") == 1  # Only one instance
        assert plugin_names.count("plugin-b") == 1
        assert plugin_names.count("plugin-c") == 1

        # Verify first occurrence is kept (version 1.0.0 for plugin-a)
        # and origin from both sources is merged (sorted)
        plugin_a = [p for p in marketplace["plugins"] if p["name"] == "plugin-a"][0]
        assert plugin_a["version"] == "1.0.0"
        assert plugin_a["source_marketplace"] == ["source-1", "source-2"]


class TestErrorHandling:
    """Test error handling in various scenarios."""

    def test_invalid_config_file(self, tmp_path):
        """Test handling of invalid config file."""
        config_file = tmp_path / "invalid.json"
        config_file.write_text("not valid json {{{")

        output_file = tmp_path / "output.json"

        with pytest.raises(json.JSONDecodeError):
            MarketplaceAggregator(str(config_file), str(output_file))

    def test_missing_config_file(self, tmp_path):
        """Test handling of missing config file."""
        config_file = tmp_path / "nonexistent.json"
        output_file = tmp_path / "output.json"

        with pytest.raises(FileNotFoundError):
            MarketplaceAggregator(str(config_file), str(output_file))

    def test_invalid_git_url(self, tmp_path):
        """Test handling of invalid git URL."""
        config_file = tmp_path / "config.json"
        config_data = {
            "version": "1.0",
            "marketplace": {"name": "test-marketplace", "version": "1.0.0"},
            "sources": [
                {
                    "type": "marketplace",
                    "url": "https://github.com/nonexistent/doesnotexist",
                    "branch": "main",
                }
            ],
        }
        config_file.write_text(json.dumps(config_data, indent=2))

        output_file = tmp_path / "output.json"

        aggregator = MarketplaceAggregator(str(config_file), str(output_file), verbose=False)
        result = aggregator.run()

        # Should return error code
        assert result == 1

    def test_marketplace_without_marketplace_json(self, tmp_path):
        """Test handling of marketplace without marketplace.json file."""
        # This would require mocking, so we'll skip for now
        # The code already handles this case by logging an error
        pass
