#!/usr/bin/env python3
"""
豆包图片 → 视频合成流水线
用法: python3 make_video.py <图片目录> <输出视频> [--fps 30] [--duration 0.5]
"""

import subprocess
import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# ========== 配置区 ==========
DEFAULT_FPS = 30
DEFAULT_DURATION = 0.5  # 每张图片停留秒数
VIDEO_CODEC = "libx264"
PRESET = "medium"
CRF = "23"
RESOLUTION = "1080:1920"  # 竖屏 9:16
# ===========================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)


def get_image_duration(img_path: str, duration: float) -> str:
    """生成 FFmpeg concat 的 duration 行"""
    return f"file '{img_path}'\nduration {duration}\n"


def build_concat_file(image_paths: list, duration: float, output_path: str) -> str:
    """构建 FFmpeg concat 文件"""
    concat_content = ""
    for i, img in enumerate(image_paths):
        concat_content += get_image_duration(img, duration)
        # 最后一张图需要再加一次（避免播放时长不足）
        if i == len(image_paths) - 1:
            concat_content += f"file '{img}'\n"
    
    concat_file = output_path.replace('.mp4', '_list.txt')
    with open(concat_file, "w") as f:
        f.write(concat_content)
    
    return concat_file


def make_video(
    image_dir: str,
    output_video: str,
    fps: int = DEFAULT_FPS,
    duration: float = DEFAULT_DURATION,
    resolution: str = RESOLUTION
) -> bool:
    """将图片目录合成为视频"""
    
    image_dir = Path(image_dir)
    
    # 查找图片
    supported = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
    image_files = sorted([
        str(f) for f in image_dir.iterdir()
        if f.suffix.lower() in supported
    ])
    
    if not image_files:
        logger.error(f"目录中未找到图片: {image_dir}")
        return False
    
    logger.info(f"找到 {len(image_files)} 张图片，开始合成视频...")
    
    # 构建 concat 文件
    concat_file = build_concat_file(image_files, duration, output_video)
    
    # FFmpeg 合成命令
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-vf", (
            f"fps={fps},"
            f"scale={resolution.split(':')[0]}:{resolution.split(':')[1]}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={resolution.split(':')[0]}:{resolution.split(':')[1]}:(ow-iw)/2:(oh-ih)/2,"
            f"format=yuv420p"
        ),
        "-c:v", VIDEO_CODEC,
        "-preset", PRESET,
        "-crf", CRF,
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_video
    ]
    
    logger.info(f"执行: {' '.join(cmd[:8])}...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg 错误: {result.stderr}")
            return False
        
        # 清理临时文件
        if os.path.exists(concat_file):
            os.remove(concat_file)
        
        # 获取视频信息
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", output_video],
            capture_output=True, text=True
        )
        
        if probe.returncode == 0:
            info = json.loads(probe.stdout)
            duration_sec = float(info['format']['duration'])
            logger.info(f"✅ 视频生成成功: {output_video}")
            logger.info(f"   时长: {duration_sec:.1f}秒, 分辨率: {RESOLUTION}")
        else:
            logger.info(f"✅ 视频生成成功: {output_video}")
        
        return True
        
    except subprocess.TimeoutExpired:
        logger.error("视频合成超时")
        return False
    except Exception as e:
        logger.error(f"合成失败: {e}")
        return False


def main():
    if len(sys.argv) < 3:
        print("用法: python3 make_video.py <图片目录> <输出视频> [选项]")
        print("示例: python3 make_video.py ~/doubao_pipeline/output video.mp4 --fps 30 --duration 0.5")
        print("")
        print("选项:")
        print("  --fps <数字>      每秒帧数 (默认: 30)")
        print("  --duration <秒>   每张图片停留时长 (默认: 0.5)")
        print("  --resolution <宽:高>  分辨率 (默认: 1080:1920 竖屏)")
        sys.exit(1)
    
    image_dir = sys.argv[1]
    output_video = sys.argv[2]
    
    fps = DEFAULT_FPS
    duration = DEFAULT_DURATION
    resolution = RESOLUTION
    
    # 解析选项
    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == "--fps" and i + 1 < len(sys.argv):
            fps = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--duration" and i + 1 < len(sys.argv):
            duration = float(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--resolution" and i + 1 < len(sys.argv):
            resolution = sys.argv[i + 1]
            i += 2
        else:
            i += 1
    
    if not os.path.isdir(image_dir):
        logger.error(f"目录不存在: {image_dir}")
        sys.exit(1)
    
    success = make_video(image_dir, output_video, fps, duration, resolution)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()