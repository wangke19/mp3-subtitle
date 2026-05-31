#!/usr/bin/env python3
"""
简单的豆包水印去除工具
使用PIL/Pillow裁掉底部水印区域
"""

import sys
from PIL import Image, ImageFilter
from pathlib import Path


def remove_watermark(input_path: str, output_path: str, method: str = "crop") -> bool:
    """去除豆包水印

    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径
        method: 处理方法 ('crop'裁剪, 'blur'模糊)
    """
    try:
        img = Image.open(input_path)
        width, height = img.size

        if method == "crop":
            # 裁掉底部8%
            crop_h = int(height * 0.08)
            cropped = img.crop((0, 0, width, height - crop_h))
            cropped.save(output_path, quality=95)
            print(f"裁剪去水印: {width}x{height} -> {cropped.size}")
            return True

        elif method == "blur":
            # 模糊底部区域
            watermark_h = int(height * 0.06)
            watermark_w = int(width * 0.30)
            x = (width - watermark_w) // 2
            y = height - watermark_h - 10

            # 裁剪水印区域
            watermark_region = img.crop((x, y, x + watermark_w, y + watermark_h))
            # 模糊处理
            blurred = watermark_region.filter(ImageFilter.GaussianBlur(radius=10))
            # 粘贴回原图
            img.paste(blurred, (x, y))
            img.save(output_path, quality=95)
            print(f"模糊去水印: 区域 ({x},{y} 大小 {watermark_w}x{watermark_h})")
            return True

        return False
    except Exception as e:
        print(f"处理失败: {e}")
        return False


def main():
    if len(sys.argv) < 3:
        print("用法: python3 watermark_removal.py <输入图片> <输出图片> [方法]")
        print("方法: crop (默认, 裁剪底部) | blur (模糊水印区域)")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    method = sys.argv[3] if len(sys.argv) > 3 else "crop"

    if not Path(input_path).exists():
        print(f"输入文件不存在: {input_path}")
        sys.exit(1)

    if remove_watermark(input_path, output_path, method):
        print(f"✅ 去水印完成: {output_path}")
        sys.exit(0)
    else:
        print(f"❌ 去水印失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
