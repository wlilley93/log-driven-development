# vibedeploy

Pre-deploy readiness analyzer for AI-generated codebases. Part of the vibe* tool family.

## Install

```bash
pip install -e .
```

## Usage

```bash
vibedeploy .                         # Scan current directory
vibedeploy . --url https://myapp.com # Add live SSL/headers/CORS checks
vibedeploy . --ship-safe             # Exit 1 if deploy blockers found
vibedeploy install --check           # Show all 84 tools with status
```
