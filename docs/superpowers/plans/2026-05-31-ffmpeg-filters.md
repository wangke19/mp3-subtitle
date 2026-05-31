# FFmpeg Filter Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-filter support to `doubao_pipeline.py` with `--filter` option for selecting color grading effects while maintaining backward compatibility.

**Architecture:** Add filter configuration dictionary, extend CLI parsing, modify `apply_color_grade()` to accept filter parameter, propagate filter through processing chain.

**Tech Stack:** Python 3, FFmpeg, argparse, existing GeminiWatermarkTool integration

---

## File Structure

**Modify:**
- `utils/doubao_pipeline/doubao_pipeline.py` - Add filter support

**No new files created.**

---

## Task 1: Add Filter Configuration Constants

**Files:**
- Modify: `utils/doubao_pipeline/doubao_pipeline.py:17-21`

- [ ] **Step 1: Add FILTERS dictionary and DEFAULT_FILTER constant**

Locate the config section (lines 17-21). After `FFMPEG_FILTER`, add:

```python
# FFmpeg filter configurations
FILTERS = {
    "basic": "eq=brightness=0.05:contrast=1.1:saturation=1.2",
    "smooth": "smooth=strength=15:threshold=10:depth=8",
    "film": "colorbalance=rs=0.2:gs=-0.1:bs=-0.15:rm=0.05:gm=0.02:bm=0.08",
    "noise": "noise=alls=2:allf=t"
}
DEFAULT_FILTER = "basic"
```

- [ ] **Step 2: Remove or comment out the old FFMPEG_FILTER line**

Replace line 19 (`FFMPEG_FILTER = "eq=brightness=0.05:contrast=1.1:saturation=1.2"`) with:
```python
# Legacy constant - replaced by FILTERS dict
# FFMPEG_FILTER = "eq=brightness=0.05:contrast=1.1:saturation=1.2"
```

- [ ] **Step 3: Verify syntax**

Run: `python3 -m py_compile utils/doubao_pipeline/doubao_pipeline.py`
Expected: No syntax errors

- [ ] **Step 4: Commit**

```bash
git add utils/doubao_pipeline/doubao_pipeline.py
git commit -m "refactor: add filter configuration constants"
```

---

## Task 2: Update apply_color_grade() Function Signature

**Files:**
- Modify: `utils/doubao_pipeline/doubao_pipeline.py:82-98`

- [ ] **Step 1: Modify function to accept filter parameter**

Change the function signature and implementation:

```python
def apply_color_grade(input_path: str, output_path: str, filter_name: str = DEFAULT_FILTER) -> bool:
    """用 FFmpeg 调色
    
    Args:
        input_path: Input image path
        output_path: Output image path
        filter_name: Filter name from FILTERS dict (default: basic)
    """
    filter_str = FILTERS.get(filter_name, FILTERS[DEFAULT_FILTER])
    
    try:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", filter_str,
            "-q:v", "2",  # JPEG 质量
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.error(f"调色超时: {input_path}")
        return False
    except Exception as e:
        logger.error(f"调色失败: {e}")
        return False
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -m py_compile utils/doubao_pipeline/doubao_pipeline.py`
Expected: No syntax errors

- [ ] **Step 3: Commit**

```bash
git add utils/doubao_pipeline/doubao_pipeline.py
git commit -m "refactor: update apply_color_grade to accept filter parameter"
```

---

## Task 3: Update process_single() Function

**Files:**
- Modify: `utils/doubao_pipeline/doubao_pipeline.py:101-143`

- [ ] **Step 1: Add filter parameter to process_single()**

Update the function signature and pass filter to apply_color_grade:

```python
def process_single(image_path: str, input_dir: str, output_dir: str, filter_name: str = DEFAULT_FILTER) -> dict:
    """处理单张图片：去水印 → 调色
    
    Args:
        image_path: Input image path
        input_dir: Input directory path
        output_dir: Output directory path
        filter_name: Filter name to apply (default: basic)
    """
```

- [ ] **Step 2: Update the apply_color_grade call inside process_single()**

Find the line that calls `apply_color_grade(temp_wm, final_path)` (around line 128) and change it to:

```python
# Step 2: 调色
if not apply_color_grade(temp_wm, final_path, filter_name):
    raise Exception("调色失败")
```

- [ ] **Step 3: Verify syntax**

Run: `python3 -m py_compile utils/doubao_pipeline/doubao_pipeline.py`
Expected: No syntax errors

- [ ] **Step 4: Commit**

```bash
git add utils/doubao_pipeline/doubao_pipeline.py
git commit -m "refactor: pass filter through process_single"
```

---

## Task 4: Add --filter CLI Argument

**Files:**
- Modify: `utils/doubao_pipeline/doubao_pipeline.py:206-223`

- [ ] **Step 1: Replace current argument parsing with argparse**

The current script uses simple sys.argv parsing. Replace the main() function's argument handling:

```python
def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='豆包图片去水印 + 调色流水线',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s ~/doubao_pipeline/input
  %(prog)s ~/doubao_pipeline/input ~/doubao_pipeline/output --filter smooth
  %(prog)s ~/doubao_pipeline/input ~/doubao_pipeline/output --filter film
        """
    )
    
    parser.add_argument('input_dir', help='输入图片目录')
    parser.add_argument('output_dir', nargs='?', help='输出目录 (默认: 输入目录)')
    parser.add_argument(
        '--filter',
        choices=list(FILTERS.keys()),
        default=DEFAULT_FILTER,
        help=f'调色滤镜 (默认: {DEFAULT_FILTER})'
    )
    
    args = parser.parse_args()
    
    input_dir = args.input_dir
    output_dir = args.output_dir
    filter_name = args.filter
    
    if not check_dependencies():
        sys.exit(1)
    
    if not os.path.isdir(input_dir):
        logger.error(f"目录不存在: {input_dir}")
        sys.exit(1)
    
    # Log the selected filter
    logger.info(f"使用滤镜: {filter_name}")
    
    batch_process(input_dir, output_dir, filter_name)
```

- [ ] **Step 2: Update batch_process() signature to accept filter parameter**

Find the `batch_process()` function definition (around line 146) and update it:

```python
def batch_process(input_dir: str, output_dir: str = None, filter_name: str = DEFAULT_FILTER) -> dict:
```

- [ ] **Step 3: Update the executor submission in batch_process()**

Find the line that submits to executor (around line 170-172) and update it:

```python
with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {
        executor.submit(process_single, str(f), str(input_dir), str(output_dir), filter_name): f
        for f in image_files
    }
```

- [ ] **Step 4: Verify syntax**

Run: `python3 -m py_compile utils/doubao_pipeline/doubao_pipeline.py`
Expected: No syntax errors

- [ ] **Step 5: Test help output**

Run: `python3 utils/doubao_pipeline/doubao_pipeline.py --help`
Expected: Show help with --filter option listing all 4 choices

- [ ] **Step 6: Commit**

```bash
git add utils/doubao_pipeline/doubao_pipeline.py
git commit -m "feat: add --filter CLI argument with argparse"
```

---

## Task 5: Add Filter Logging

**Files:**
- Modify: `utils/doubao_pipeline/doubao_pipeline.py:82-98`

- [ ] **Step 1: Add logging statement in apply_color_grade()**

Add a log line before the FFmpeg command:

```python
def apply_color_grade(input_path: str, output_path: str, filter_name: str = DEFAULT_FILTER) -> bool:
    """用 FFmpeg 调色"""
    filter_str = FILTERS.get(filter_name, FILTERS[DEFAULT_FILTER])
    logger.info(f"应用滤镜: {filter_name} ({filter_str})")
    
    try:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", filter_str,
            "-q:v", "2",
            output_path
        ]
        # ... rest unchanged
```

- [ ] **Step 2: Verify syntax**

Run: `python3 -m py_compile utils/doubao_pipeline/doubao_pipeline.py`
Expected: No syntax errors

- [ ] **Step 3: Commit**

```bash
git add utils/doubao_pipeline/doubao_pipeline.py
git commit -m "feat: add filter logging"
```

---

## Task 6: Create Test Images

**Files:**
- Create: `utils/doubao_pipeline/test_input/`

- [ ] **Step 1: Create test directory**

```bash
mkdir -p utils/doubao_pipeline/test_input
```

- [ ] **Step 2: Copy a test image**

```bash
# Use an existing image from the project or create a simple test image
cp imgs/*.jpg utils/doubao_pipeline/test_input/ 2>/dev/null || \
cp imgs/*.png utils/doubao_pipeline/test_input/ 2>/dev/null || \
echo "No test images found in imgs/, please add one manually"
```

- [ ] **Step 3: Verify test image exists**

Run: `ls utils/doubao_pipeline/test_input/`
Expected: At least one image file

- [ ] **Step 4: Commit**

```bash
git add utils/doubao_pipeline/test_input/
git commit -m "test: add test input directory"
```

---

## Task 7: Test Each Filter

**Files:**
- Test: `utils/doubao_pipeline/doubao_pipeline.py` (integration test)

- [ ] **Step 1: Test basic filter (default)**

```bash
mkdir -p utils/doubao_pipeline/test_output_basic
python3 utils/doubao_pipeline/doubao_pipeline.py \
  utils/doubao_pipeline/test_input \
  utils/doubao_pipeline/test_output_basic
```
Expected: Output in `test_output_basic/` with `*_clean.jpg` files

- [ ] **Step 2: Verify basic filter output exists**

```bash
ls utils/doubao_pipeline/test_output_basic/
```
Expected: At least one `*_clean.jpg` file

- [ ] **Step 3: Test smooth filter**

```bash
mkdir -p utils/doubao_pipeline/test_output_smooth
python3 utils/doubao_pipeline/doubao_pipeline.py \
  utils/doubao_pipeline/test_input \
  utils/doubao_pipeline/test_output_smooth \
  --filter smooth
```
Expected: Output in `test_output_smooth/`

- [ ] **Step 4: Verify smooth filter output**

```bash
ls utils/doubao_pipeline/test_output_smooth/
```
Expected: At least one `*_clean.jpg` file

- [ ] **Step 5: Test film filter**

```bash
mkdir -p utils/doubao_pipeline/test_output_film
python3 utils/doubao_pipeline/doubao_pipeline.py \
  utils/doubao_pipeline/test_input \
  utils/doubao_pipeline/test_output_film \
  --filter film
```
Expected: Output in `test_output_film/`

- [ ] **Step 6: Verify film filter output**

```bash
ls utils/doubao_pipeline/test_output_film/
```
Expected: At least one `*_clean.jpg` file

- [ ] **Step 7: Test noise filter**

```bash
mkdir -p utils/doubao_pipeline/test_output_noise
python3 utils/doubao_pipeline/doubao_pipeline.py \
  utils/doubao_pipeline/test_input \
  utils/doubao_pipeline/test_output_noise \
  --filter noise
```
Expected: Output in `test_output_noise/`

- [ ] **Step 8: Verify noise filter output**

```bash
ls utils/doubao_pipeline/test_output_noise/
```
Expected: At least one `*_clean.jpg` file

- [ ] **Step 9: Test invalid filter rejection**

```bash
python3 utils/doubao_pipeline/doubao_pipeline.py \
  utils/doubao_pipeline/test_input \
  utils/doubao_pipeline/test_output_invalid \
  --filter nonexistent 2>&1 | head -5
```
Expected: Error message about invalid choice

- [ ] **Step 10: Commit test outputs (optional)**

```bash
git add utils/doubao_pipeline/test_*/
git commit -m "test: verify all filters produce valid output"
```

---

## Task 8: Verify Backward Compatibility

**Files:**
- Test: `utils/doubao_pipeline/doubao_pipeline.py`

- [ ] **Step 1: Test default behavior without --filter flag**

```bash
rm -rf utils/doubao_pipeline/test_compat
mkdir -p utils/doubao_pipeline/test_compat
python3 utils/doubao_pipeline/doubao_pipeline.py \
  utils/doubao_pipeline/test_input \
  utils/doubao_pipeline/test_compat
```
Expected: Uses basic filter by default, same as Task 7 Step 1

- [ ] **Step 2: Compare with explicit basic filter**

```bash
# Compare file sizes (should be similar for same input)
ls -l utils/doubao_pipeline/test_compat/*clean*.jpg
ls -l utils/doubao_pipeline/test_output_basic/*clean*.jpg
```
Expected: Similar file sizes (may differ slightly due to FFmpeg non-determinism)

- [ ] **Step 3: Test single-argument invocation (no output dir)**

```bash
cd utils/doubao_pipeline/test_input
python3 ../doubao_pipeline.py .
cd -
```
Expected: Processes files in-place in test_input directory

- [ ] **Step 4: Clean up test files from in-place test**

```bash
rm -f utils/doubao_pipeline/test_input/*clean*.jpg
```

- [ ] **Step 5: Verify help message**

```bash
python3 utils/doubao_pipeline/doubao_pipeline.py --help
```
Expected: Shows help with all options including --filter

- [ ] **Step 6: Commit compatibility verification notes**

```bash
git update-index --assume-unchanged utils/doubao_pipeline/test_*/
git commit --allow-empty -m "test: verify backward compatibility maintained"
```

---

## Task 9: Final Integration Test

**Files:**
- Test: Full pipeline with make_video.py

- [ ] **Step 1: Run complete pipeline with smooth filter**

```bash
rm -rf utils/doubao_pipeline/final_test
mkdir -p utils/doubao_pipeline/final_test
python3 utils/doubao_pipeline/doubao_pipeline.py \
  utils/doubao_pipeline/test_input \
  utils/doubao_pipeline/final_test \
  --filter smooth
```
Expected: Clean images in `final_test/`

- [ ] **Step 2: Create video from processed images**

```bash
python3 utils/doubao_pipeline/make_video.py \
  utils/doubao_pipeline/final_test \
  utils/doubao_pipeline/final_test_output.mp4 \
  --fps 30 --duration 1
```
Expected: Video file created

- [ ] **Step 3: Verify video exists**

```bash
ls -lh utils/doubao_pipeline/final_test_output.mp4
```
Expected: File exists with reasonable size (>0 bytes)

- [ ] **Step 4: Check video info**

```bash
ffprobe -v quiet -print_format json -show_format -show_streams \
  utils/doubao_pipeline/final_test_output.mp4 | python3 -m json.tool
```
Expected: Valid video metadata shown

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete FFmpeg filter enhancement implementation"
```

---

## Self-Review Checklist

After completing all tasks:

- [ ] All filters (basic, smooth, film, noise) produce valid output
- [ ] Default behavior unchanged (uses basic filter)
- [ ] `--help` shows correct usage
- [ ] Invalid filter names are rejected
- [ ] Integration with make_video.py works
- [ ] No placeholder text or TODOs in code
- [ ] All commits have descriptive messages
- [ ] Code compiles without syntax errors
