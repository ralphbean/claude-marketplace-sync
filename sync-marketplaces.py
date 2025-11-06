#!/usr/bin/env python3
"""
Claude Code Marketplace Aggregator

Recursively syncs plugins from multiple child marketplaces into a parent marketplace,
with support for denylisting specific skills and tracking provenance.

Usage:
    python sync-marketplaces.py [--config .sync-config.json] [--output .claude-plugin/marketplace.json]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from urllib.parse import urlparse
import re


class MarketplaceAggregator:
    """Aggregates multiple Claude Code marketplaces into a single marketplace."""

    def __init__(self, config_path: str, output_path: str, verbose: bool = False):
        self.config_path = Path(config_path)
        self.output_path = Path(output_path)
        self.verbose = verbose
        self.temp_dir = None
        self.processed_marketplaces: Set[str] = set()
        self.all_plugins: List[Dict] = []
        self.provenance_map: Dict[str, List[str]] = {}  # plugin_name -> [marketplace_chain]

        # Load configuration
        with open(self.config_path) as f:
            self.config = json.load(f)

    def log(self, message: str, level: str = "info"):
        """Log a message if verbose mode is enabled."""
        if self.verbose or level == "error":
            prefix = "ERROR" if level == "error" else "INFO"
            print(f"[{prefix}] {message}", file=sys.stderr if level == "error" else sys.stdout)

    def run(self):
        """Main entry point for the aggregator."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                self.temp_dir = Path(temp_dir)
                self.log(f"Using temporary directory: {self.temp_dir}")

                # Process all sources (only immediate children)
                for source in self.config.get("sources", []):
                    self._process_source(source, parent_chain=[])

                # Generate final marketplace.json
                self._generate_marketplace()

                self.log("✓ Marketplace aggregation complete!")
                return 0
        except Exception as e:
            self.log(f"Failed to aggregate marketplace: {e}", level="error")
            import traceback

            traceback.print_exc()
            return 1

    def _process_source(self, source: Dict, parent_chain: List[str]):
        """Process a single source (marketplace or skill)."""
        source_type = source.get("type", "skill")

        if source_type == "marketplace":
            self._process_marketplace(source, parent_chain)
        elif source_type == "skill":
            self._process_skill(source, parent_chain)
        else:
            self.log(f"Unknown source type: {source_type}", level="error")

    def _process_marketplace(self, source: Dict, parent_chain: List[str]):
        """Process a marketplace source by pulling all its plugins (non-recursive)."""
        url = source["url"]
        branch = source.get("branch", "main")
        denylist = set(source.get("denylist", []))
        tag_prefix = source.get("tag_prefix", self._extract_repo_name(url))

        # Avoid processing the same marketplace twice
        marketplace_id = f"{url}@{branch}"
        if marketplace_id in self.processed_marketplaces:
            self.log(f"Already processed {marketplace_id}, skipping")
            return

        self.processed_marketplaces.add(marketplace_id)
        self.log(f"Processing marketplace: {url} (branch: {branch})")

        # Clone the marketplace
        clone_dir = self.temp_dir / f"marketplace-{len(self.processed_marketplaces)}"
        self._clone_repo(url, branch, clone_dir)

        # Read the marketplace.json
        marketplace_file = clone_dir / ".claude-plugin" / "marketplace.json"
        if not marketplace_file.exists():
            self.log(f"No marketplace.json found in {url}", level="error")
            return

        with open(marketplace_file) as f:
            marketplace_data = json.load(f)

        # Process plugins from this marketplace (only immediate children, not recursive)
        new_parent_chain = parent_chain + [tag_prefix]

        for plugin in marketplace_data.get("plugins", []):
            plugin_name = plugin["name"]

            # Check denylist
            if plugin_name in denylist:
                self.log(f"  Skipping denylisted plugin: {plugin_name}")
                continue

            # Add provenance
            plugin_copy = plugin.copy()
            provenance_field = self.config.get("sync_settings", {}).get(
                "provenance_field", "source_marketplace"
            )
            plugin_copy[provenance_field] = "/".join(new_parent_chain)

            # Track provenance
            if plugin_name not in self.provenance_map:
                self.provenance_map[plugin_name] = []
            self.provenance_map[plugin_name].append("/".join(new_parent_chain))

            self.log(f"  Adding plugin: {plugin_name} (from {'/'.join(new_parent_chain)})")
            self.all_plugins.append(plugin_copy)

        self.log(
            f"✓ Processed {len(marketplace_data.get('plugins', []))} plugins from {tag_prefix}"
        )

    def _process_skill(self, source: Dict, parent_chain: List[str]):
        """Process a single skill source."""
        name = source["name"]
        url = source["url"]
        branch = source.get("branch", "main")
        target_path = source.get("target_path", f"skills/{name}")

        self.log(f"Processing skill: {name} from {url}")

        # Clone the skill
        clone_dir = self.temp_dir / f"skill-{name}"
        self._clone_repo(url, branch, clone_dir)

        # Copy skill to target location (in parent repo)
        parent_dir = (
            self.output_path.parent.parent
        )  # Assuming output is .claude-plugin/marketplace.json
        target = parent_dir / target_path

        # Remove existing content
        if target.exists():
            shutil.rmtree(target)

        # Copy new content (exclude .git)
        shutil.copytree(
            clone_dir,
            target,
            ignore=shutil.ignore_patterns(
                *self.config.get("sync_settings", {}).get("exclude_patterns", [".git"])
            ),
        )

        # Extract version from SKILL.md if present
        version = self._extract_version_from_skill(target / "SKILL.md")

        # Create plugin entry
        provenance_field = self.config.get("sync_settings", {}).get(
            "provenance_field", "source_marketplace"
        )
        plugin_entry = {
            "name": name,
            "description": source.get("description", f"Skill: {name}"),
            "version": version,
            "source": f"./{target_path}",
            "category": source.get("category", "skills"),
            provenance_field: "/".join(parent_chain) if parent_chain else "direct",
        }

        self.all_plugins.append(plugin_entry)
        self.log(f"✓ Added skill: {name} (version: {version})")

    def _clone_repo(self, url: str, branch: str, target_dir: Path):
        """Clone a git repository."""
        self.log(f"Cloning {url} (branch: {branch}) to {target_dir}")

        # Support both GitHub/GitLab URLs
        # Disable credential prompts to prevent hanging on invalid URLs
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"  # Disable credential prompts
        env["GIT_ASKPASS"] = "true"  # Use /bin/true for askpass (returns nothing)

        try:
            subprocess.run(
                ["git", "clone", "--branch", branch, "--depth", "1", url, str(target_dir)],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
        except subprocess.CalledProcessError as e:
            self.log(f"Failed to clone {url}: {e.stderr}", level="error")
            raise

    def _extract_repo_name(self, url: str) -> str:
        """Extract a reasonable name from a git URL."""
        # Handle various URL formats
        # https://github.com/owner/repo.git -> repo
        # git@github.com:owner/repo.git -> repo
        # https://github.com/owner/repo -> repo

        path = urlparse(url).path if url.startswith("http") else url.split(":")[-1]
        name = path.rstrip("/").split("/")[-1]
        name = name.replace(".git", "")
        return name

    def _extract_version_from_skill(self, skill_md_path: Path) -> str:
        """Extract semantic version from SKILL.md file."""
        if not skill_md_path.exists():
            return "1.0.0"

        try:
            with open(skill_md_path) as f:
                content = f.read()

            # Try YAML frontmatter first
            frontmatter_match = re.search(
                r'^---\s*\nversion:\s*["\']?([0-9.]+)["\']?\s*\n', content, re.MULTILINE
            )
            if frontmatter_match:
                return frontmatter_match.group(1)

            # Try metadata section
            metadata_match = re.search(
                r'##\s*Skill Metadata.*?version:\s*["\']?([0-9.]+)["\']?',
                content,
                re.DOTALL | re.IGNORECASE,
            )
            if metadata_match:
                return metadata_match.group(1)

            return "1.0.0"
        except Exception as e:
            self.log(f"Failed to extract version from {skill_md_path}: {e}", level="error")
            return "1.0.0"

    def _generate_marketplace(self):
        """Generate the final marketplace.json file."""
        marketplace_config = self.config.get("marketplace", {})

        # Deduplicate plugins (prefer first occurrence to respect priority)
        seen_names = set()
        unique_plugins = []

        for plugin in self.all_plugins:
            name = plugin["name"]
            if name not in seen_names:
                seen_names.add(name)
                unique_plugins.append(plugin)
            else:
                self.log(
                    f"Duplicate plugin '{name}' found, keeping first occurrence from: {plugin.get('source_marketplace', 'unknown')}"
                )

        # Build marketplace structure
        marketplace_data = {
            "name": marketplace_config.get("name", "aggregated-marketplace"),
            "version": marketplace_config.get("version", "1.0.0"),
            "description": marketplace_config.get(
                "description", "Aggregated Claude Code marketplace"
            ),
            "owner": marketplace_config.get(
                "owner", {"name": "Marketplace Aggregator", "email": "noreply@example.com"}
            ),
            "plugins": unique_plugins,
        }

        # Write to output file
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w") as f:
            json.dump(marketplace_data, f, indent=2)

        self.log(
            f"✓ Generated marketplace.json with {len(unique_plugins)} plugins at {self.output_path}"
        )

        # Print summary
        print("\n=== Aggregation Summary ===")
        print(f"Total plugins: {len(unique_plugins)}")
        print(f"Total marketplaces processed: {len(self.processed_marketplaces)}")
        print(f"Output: {self.output_path}")

        if self.provenance_map:
            print("\n=== Provenance Summary ===")
            for plugin_name, sources in sorted(self.provenance_map.items()):
                print(f"  {plugin_name}: {', '.join(sources)}")


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate multiple Claude Code marketplaces into a single marketplace"
    )
    parser.add_argument(
        "--config",
        default=".sync-config.json",
        help="Path to sync configuration file (default: .sync-config.json)",
    )
    parser.add_argument(
        "--output",
        default=".claude-plugin/marketplace.json",
        help="Path to output marketplace.json file (default: .claude-plugin/marketplace.json)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    aggregator = MarketplaceAggregator(args.config, args.output, args.verbose)
    sys.exit(aggregator.run())


if __name__ == "__main__":
    main()
