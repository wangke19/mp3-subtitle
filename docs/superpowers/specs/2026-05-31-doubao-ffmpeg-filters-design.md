# FFmpeg Filter Enhancement for Doubao Pipeline

**Date:** 2026-05-31
**Status:** Approved
**Type:** Enhancement

## Overview

Add multi-filter support to the existing Doubao watermark removal pipeline while maintaining backward compatibility. Users can select different color grading effects via a `--filter` command-line option.

## Filter Options

| Filter ID | Description | FFmpeg Parameters |
|-----------|-------------|-------------------|
| `basic` (default) | Current behavior - brightness/contrast/saturation adjustment | `eq=brightness=0.05:contrast=1.1:saturation=1.2` |
| `smooth` | Soften image to hide AI generation traces | `smooth=strength=15:threshold=10:depth=8` |
| `film` | Film-style color grading with color balance | `colorbalance=rs=0.2:gs=-0.1:bs=-0.15:rm=0.05:gm=0.02:bm=0.08` |
| `noise` | Add subtle noise to reduce AI characteristics | `noise=alls=2:allf=t` |

## Changes to `doubao_pipeline.py`

### 1. Add Filter Constants
Define filter configurations at module level:
```python
FILTERS = {
    "basic": "eq=brightness=0.05:contrast=1.1:saturation=1.2",
    "smooth": "smooth=strength=15:threshold=10:depth=8",
    "film": "colorbalance=rs=0.2:gs=-0.1:bs=-0.15:rm=0.05:gm=0.02:bm=0.08",
    "noise": "noise=alls=2:allf=t"
}
DEFAULT_FILTER = "basic"
```

### 2. Add `--filter` CLI Argument
Extend `main()` to parse filter option:
```python
parser.add_argument("--filter", choices=list(FILTERS.keys()),
                    default=DEFAULT_FILTER,
                    help="Color grading filter to apply")
```

### 3. Modify `apply_color_grade()`
Change signature to accept filter parameter:
```python
def apply_color_grade(input_path: str, output_path: str, filter_name: str = DEFAULT_FILTER) -> bool:
    """Apply FFmpeg color grading filter"""
    filter_str = FILTERS.get(filter_name, FILTERS[DEFAULT_FILTER])
    # ... rest of implementation
```

### 4. Update Logging
Add informational message showing which filter is being applied:
```python
logger.info(f"Applying filter: {filter_name} ({filter_str})")
```

### 5. Update `process_single()`
Pass filter parameter through the processing chain.

## Usage Examples

```bash
# Default behavior (basic filter - backward compatible)
python3 doubao_pipeline.py ~/doubao_pipeline/input

# Select specific filter
python3 doubao_pipeline.py ~/doubao_pipeline/input --filter smooth
python3 doubao_pipeline.py ~/doubao_pipeline/input --filter film
python3 doubao_pipeline.py ~/doubao_pipeline/input --filter noise

# With output directory
python3 doubao_pipeline.py ~/doubao_pipeline/input ~/doubao_pipeline/output --filter film
```

## File Structure

No changes to directory structure:
```
utils/doubao_pipeline/
├── doubao_pipeline.py   # Enhanced with filter support
├── make_video.py        # Unchanged
└── setup.sh             # Unchanged
```

## Backward Compatibility

- Default behavior unchanged: uses `basic` filter with existing parameters
- Existing scripts continue to work without modification
- All existing command-line arguments preserved

## Testing Considerations

- Test each filter produces valid output images
- Verify default behavior matches current implementation
- Test invalid filter name is rejected
- Verify parallel processing works with filter parameter
