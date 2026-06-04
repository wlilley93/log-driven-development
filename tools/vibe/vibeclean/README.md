# vibeclean

Detect AI-generated code slop, spaghetti, and hygiene issues.

The tool for the specific kind of mess that LLM-assisted coding produces. It catches the patterns that developers complain about when they talk about "AI slop code."

## Install

```bash
pip install vibeclean
```

## Usage

```bash
# Scan current directory
vibeclean

# Scan a specific path
vibeclean /path/to/project

# Run specific runners only
vibeclean --runners dead_code,complexity

# Skip certain runners
vibeclean --skip convention,duplication

# Output as JSON
vibeclean --output json --json-pretty

# Output as markdown (for PR comments)
vibeclean --output md --output-file report.md

# Show fix hints
vibeclean --fix

# Fail on medium+ severity (default: high)
vibeclean --fail-on medium
```

## Runners

### dead_code
AST-based detection of unused and unreachable code:
- Unused imports
- Unused variables (assigned but never read)
- Unreachable code after return/raise/break/continue
- Empty function bodies (just `pass` or `...`)
- Orphaned files not imported by anything

### slop_detector
The AI slop signature patterns:
- Redundant comments that restate the code
- Docstrings on obvious one-liner methods
- Unnecessary try/except that just re-raises
- TODO/FIXME comments left in code
- Debug print statements
- Type annotations that add no value (`Any`, `object`)

### complexity
Structural complexity issues:
- Functions over 50 lines
- Deeply nested code (>4 levels)
- God files (>500 lines with >10 top-level definitions)
- Circular import detection
- Too many parameters (>6 args)

### duplication
Copy-paste detection:
- Identical or near-identical function bodies
- Repeated code blocks (>5 consecutive similar lines appearing 3+ times)
- Identical except blocks across the codebase

### convention
Consistency checks:
- Mixed naming conventions (camelCase + snake_case)
- Inconsistent string quotes within a file
- Mixed indentation (tabs vs spaces)
- Inconsistent import style (relative vs absolute)
- Files missing `__all__` when they define public API

## Configuration

Create a `.vibeclean.yml` in your project root:

```yaml
fail_on: HIGH

runners:
  complexity:
    max_function_lines: 50
    max_nesting_depth: 4
    max_parameters: 6
  duplication:
    min_duplicate_lines: 5
    min_occurrences: 3

exclude:
  - "*.pyc"
  - "__pycache__"
  - ".venv"
  - "node_modules"

ignore_rules:
  - "dead_code:orphaned-file"
  - "convention:mixed-quotes"
```

## Categories

Findings are grouped into five categories: `DEAD_CODE`, `SLOP`, `COMPLEXITY`, `DUPLICATION`, `CONVENTION`.
