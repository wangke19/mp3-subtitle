#!/usr/bin/env python3
"""
豆包水印去除工具 - 图像处理方法
去除底部"豆包AI生成"文字水印
"""

import sys
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
from pathlib import Path


def remove_watermark_blur(input_path: str, output_path: str) -> bool:
    """去除豆包水印 - 使用背景色覆盖 + 边缘模糊"""
    try:
        img = Image.open(input_path)
        width, height = img.size

        # 豆包水印在底部中间区域
        watermark_h = int(height * 0.06)
        watermark_w = int(width * 0.30)
        x = (width - watermark_w) // 2
        y = height - watermark_h - 10

        print(f"覆盖水印区域: ({x}, {y} 大小 {watermark_w}x{watermark_h})")

        # 获取水印上方背景区域的平均颜色
        bg_region = img.crop((x, y - 30, x + watermark_w, y))
        bg_colors = list(bg_region.getdata())

        # 计算平均RGB
        if bg_colors:
            avg_r = sum(c[0] for c in bg_colors) // len(bg_colors)
            avg_g = sum(c[1] for c in bg_colors) // len(bg_colors)
            avg_b = sum(c[2] for c in bg_colors) // len(bg_colors)
            fill_color = (avg_r, avg_g, avg_b)
        else:
            fill_color = (255, 255, 255)  # 默认白色

        # 创建新的水印区域，填充背景色
        watermark_region = Image.new('RGB', (watermark_w, watermark_h), fill_color)

        # 对边缘区域做轻微模糊以融合
        blurred_top = watermark_region.filter(ImageFilter.GaussianBlur(radius=3))
        blurred_bottom = watermark_region.filter(ImageFilter.GaussianBlur(radius=3))

        # 粘贴回原图
        img.paste(blurred_top, (x, y))

        img.save(output_path, quality=95)
        print(f"✅ 去水印完成: {output_path}")
        return True

    except Exception as e:
        print(f"❌ 去水印失败: {e}")
        return False


def remove_watermark_crop(input_path: str, output_path: str) -> bool:
    """裁剪底部去除水印（简单方案）"""
    try:
        img = Image.open(input_path)
        width, height = img.size

        # 裁掉底部8%
        crop_h = int(height * 0.08)
        cropped = img.crop((0, 0, width, height - crop_h))

        cropped.save(output_path, quality=95)
        print(f"✅ 裁剪去水印: {width}x{height} -> {cropped.size}")
        return True
    except Exception as e:
        print(f"❌ 裁剪失败: {e}")
        return False


def main():
    if len(sys.argv) < 3:
        print("用法: python3 watermark_removal.py <输入图片> <输出图片> [方法]")
        print("方法: blur (默认, 强力模糊) | crop (裁剪底部)")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    method = sys.argv[3] if len(sys.argv) > 3 else "blur"

    if not Path(input_path).exists():
        print(f"输入文件不存在: {input_path}")
        sys.exit(1)

    if method == "crop":
        success = remove_watermark_crop(input_path, output_path)
    else:
        success = remove_watermark_blur(input_path, output_path)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
