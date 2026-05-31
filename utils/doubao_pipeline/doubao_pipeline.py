#!/usr/bin/env python3
"""
豆包图片去水印 + 调色流水线
用法: python3 doubao_pipeline.py <输入目录> [输出目录]
"""

import subprocess
import os
import sys
import logging
import hashlib
import json
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

# ========== 配置区 ==========
GEMINI_TOOL_PATH = os.path.expanduser("~/doubao_pipeline/bin/GeminiWatermarkTool")

# FFmpeg filter configurations
FILTERS = {
    "basic": "eq=brightness=0.05:contrast=1.1:saturation=1.2",
    "smooth": "smooth=strength=15:threshold=10:depth=8",
    "film": "colorbalance=rs=0.2:gs=-0.1:bs=-0.15:rm=0.05:gm=0.02:bm=0.08",
    "noise": "noise=alls=2:allf=t"
}
DEFAULT_FILTER = "basic"

# Legacy constant - replaced by FILTERS dict
# FFMPEG_FILTER = "eq=brightness=0.05:contrast=1.1:saturation=1.2"

MAX_WORKERS = 4
# ===========================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(os.path.expanduser("~/doubao_pipeline/logs/pipeline.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """检查依赖工具"""
    tools = ["ffmpeg", "python3"]
    missing = []
    for tool in tools:
        result = subprocess.run(f"which {tool}", shell=True, capture_output=True)
        if result.returncode != 0:
            missing.append(tool)
    if missing:
        logger.error(f"缺少工具: {', '.join(missing)}")
        logger.info("安装命令: sudo apt install ffmpeg  # Debian/Ubuntu")
        logger.info("          brew install ffmpeg      # macOS")
        return False
    return True


def remove_watermark(input_path: str, output_path: str) -> bool:
    """调用 GeminiWatermarkTool 去除水印"""
    cli_path = os.path.join(GEMINI_TOOL_PATH, "cli.py")
    
    if not os.path.exists(cli_path):
        # fallback: 尝试直接从 pip 安装的版本
        try:
            result = subprocess.run(
                ["gemini-watermark-tool", "--input", input_path, "--output", output_path],
                capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0
        except:
            pass
        
        logger.error(f"未找到 GeminiWatermarkTool: {cli_path}")
        return False
    
    try:
        result = subprocess.run(
            ["python3", cli_path, "--input", input_path, "--output", output_path, "--mode", "auto"],
            capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.error(f"去水印超时: {input_path}")
        return False
    except Exception as e:
        logger.error(f"去水印失败: {e}")
        return False


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


def process_single(image_path: str, input_dir: str, output_dir: str, filter_name: str = DEFAULT_FILTER) -> dict:
    """处理单张图片：去水印 → 调色

    Args:
        image_path: Input image path
        input_dir: Input directory path
        output_dir: Output directory path
        filter_name: Filter name to apply (default: basic)
    """
    filename = Path(image_path).name
    stem = Path(image_path).stem
    ext = Path(image_path).suffix.lower()
    
    # 中间文件（去水印后）
    temp_wm = os.path.join(output_dir, f".tmp_wm_{stem}{ext}")
    # 最终输出（调色后）
    final_path = os.path.join(output_dir, f"{stem}_clean{ext}")
    
    result = {
        "file": filename,
        "status": "pending",
        "watermark_removed": False,
        "color_graded": False,
        "output": None,
        "error": None
    }
    
    try:
        # Step 1: 去水印
        if not remove_watermark(image_path, temp_wm):
            raise Exception("去水印失败")
        result["watermark_removed"] = True
        
        # Step 2: 调色
        if not apply_color_grade(temp_wm, final_path, filter_name):
            raise Exception("调色失败")
        result["color_graded"] = True
        
        result["status"] = "success"
        result["output"] = final_path
        
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
    finally:
        # 清理临时文件
        if os.path.exists(temp_wm):
            os.remove(temp_wm)
    
    return result


def batch_process(input_dir: str, output_dir: str = None, filter_name: str = DEFAULT_FILTER) -> dict:
    """批量处理目录"""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir) if output_dir else input_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 支持的图片格式
    supported = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
    image_files = sorted([
        f for f in input_dir.iterdir() 
        if f.suffix.lower() in supported
    ])
    
    if not image_files:
        logger.warning(f"目录中未找到图片: {input_dir}")
        return {"total": 0, "success": 0, "failed": 0, "results": []}
    
    logger.info(f"找到 {len(image_files)} 张图片，开始处理...")
    
    results = []
    success_count = 0
    failed_count = 0
    
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_single, str(f), str(input_dir), str(output_dir), filter_name): f
            for f in image_files
        }
        
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            
            if res["status"] == "success":
                success_count += 1
                logger.info(f"✅ {res['file']} → {res['output']}")
            else:
                failed_count += 1
                logger.error(f"❌ {res['file']}: {res['error']}")
    
    summary = {
        "total": len(image_files),
        "success": success_count,
        "failed": failed_count,
        "results": results,
        "timestamp": datetime.now().isoformat()
    }
    
    # 保存处理报告
    report_path = output_dir / "process_report.json"
    with open(report_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n处理完成: 成功 {success_count}/{len(image_files)}")
    if failed_count > 0:
        logger.warning(f"失败 {failed_count} 张，详见 {report_path}")
    
    return summary


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


if __name__ == "__main__":
    main()