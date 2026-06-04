"""Runner for sharp — image metadata analysis for oversized assets."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from viberapid.models import ToolResult, ToolStatus
from viberapid.normalisers.sharp_check import SharpCheckNormaliser
from viberapid.runners.base import AsyncToolRunner

# Inline Node.js script that uses sharp to read image metadata.
# Accepts a JSON array of file paths on stdin and outputs metadata for each.
_SHARP_SCRIPT = """\
const sharp = require('sharp');
const fs = require('fs');

const input = fs.readFileSync(0, 'utf-8');
const files = JSON.parse(input);

async function analyse(files) {
  const results = [];
  for (const filePath of files) {
    try {
      const metadata = await sharp(filePath).metadata();
      const stats = fs.statSync(filePath);
      results.push({
        file: filePath,
        width: metadata.width || 0,
        height: metadata.height || 0,
        format: metadata.format || 'unknown',
        channels: metadata.channels || 0,
        hasAlpha: metadata.hasAlpha || false,
        size: stats.size,
        space: metadata.space || 'unknown',
        density: metadata.density || 72,
      });
    } catch (err) {
      results.push({
        file: filePath,
        error: err.message,
      });
    }
  }
  process.stdout.write(JSON.stringify(results));
}

analyse(files).catch(err => {
  process.stderr.write(err.message);
  process.exit(1);
});
"""


class SharpCheckRunner(AsyncToolRunner):
    """Use sharp (Node.js) to analyse image metadata and detect oversized
    assets. Flags images that are larger than necessary based on their
    dimensions, format, and file size."""

    name = "sharp-check"
    requires_node = True

    def should_run(self) -> bool:
        image_files = self._glob_files(
            "*.png", "*.jpg", "*.jpeg", "*.webp", "*.avif",
            "*.gif", "*.tiff", "*.tif",
        )
        image_files = [
            f for f in image_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and ".git" not in str(f)
        ]
        if not image_files:
            self.skip_reason = "no image files found"
            return False
        return True

    def run(self, changed_files: list[str] | None = None) -> ToolResult:
        image_files = self._glob_files(
            "*.png", "*.jpg", "*.jpeg", "*.webp", "*.avif",
            "*.gif", "*.tiff", "*.tif",
        )
        image_files = [
            f for f in image_files
            if "node_modules" not in str(f)
            and ".next" not in str(f)
            and ".git" not in str(f)
        ]

        if not image_files:
            return ToolResult(
                tool=self.name,
                status=ToolStatus.SUCCESS,
                findings=[],
                metrics={"images_checked": 0},
            )

        npx = self._npx_path()

        # Limit to 100 images to avoid excessive processing
        file_paths = [str(f) for f in image_files[:100]]

        with tempfile.TemporaryDirectory(prefix="viberapid-sharp-") as tmp_dir:
            # Write the analysis script
            script_path = Path(tmp_dir) / "analyse.js"
            script_path.write_text(_SHARP_SCRIPT)

            # Pipe file list as JSON via stdin
            file_list_json = json.dumps(file_paths)

            cmd = [npx, "--yes", "sharp-cli", "--version"]
            # Actually, sharp is a library, not a CLI. We need to run via node.
            # Use node directly with sharp installed via npx context.
            cmd = [
                npx, "-p", "sharp",
                "node", str(script_path),
            ]

            result = self._exec(cmd, timeout=120, input_data=file_list_json)

            if result.returncode != 0 or not result.stdout.strip():
                # Fallback: try with node directly (sharp may be globally installed)
                import shutil
                node_bin = shutil.which("node")
                if node_bin:
                    cmd = [node_bin, str(script_path)]
                    result = self._exec(cmd, timeout=120, input_data=file_list_json)

            if not result.stdout.strip():
                return self._make_error_result(
                    f"sharp analysis produced no output. stderr: {result.stderr.strip()[:500]}"
                )

            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError:
                return self._make_error_result(
                    f"sharp analysis produced non-JSON output. stderr: {result.stderr.strip()[:500]}"
                )

        # Convert absolute paths to relative
        for entry in data:
            if isinstance(entry, dict) and "file" in entry:
                try:
                    entry["file"] = str(Path(entry["file"]).relative_to(self.target))
                except ValueError:
                    pass

        normaliser = SharpCheckNormaliser()
        findings = normaliser.normalise(data)

        total_size = sum(
            entry.get("size", 0)
            for entry in data
            if isinstance(entry, dict) and "error" not in entry
        )

        return ToolResult(
            tool=self.name,
            status=ToolStatus.SUCCESS,
            findings=findings,
            metrics={
                "images_checked": len(data),
                "total_image_bytes": total_size,
                "images_over_1mb": sum(
                    1 for e in data
                    if isinstance(e, dict) and e.get("size", 0) > 1_048_576
                ),
                "images_over_2000px": sum(
                    1 for e in data
                    if isinstance(e, dict)
                    and (e.get("width", 0) > 2000 or e.get("height", 0) > 2000)
                ),
            },
        )
