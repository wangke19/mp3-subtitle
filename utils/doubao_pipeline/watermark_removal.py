#!/usr/bin/env python3
"""
豆包水印去除工具 - 图像处理方法
去除底部"豆包AI生成"文字水印
"""

import sys
import numpy as np
from PIL import Image, ImageFilter
from pathlib import Path


def remove_watermark_doubao(input_path: str, output_path: str) -> bool:
    """去除豆包水印 - 使用inpainting方法

    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径
    """
    try:
        img = Image.open(input_path)
        width, height = img.size

        # 豆包水印通常在底部中间区域
        watermark_h = int(height * 0.06)
        watermark_w = int(width * 0.30)
        x = (width - watermark_w) // 2
        y = height - watermark_h - 10

        print(f"检测到水印区域: ({x}, {y} 大小 {watermark_w}x{watermark_h})")

        # 转换为numpy数组进行处理
        img_array = np.array(img)

        # 提取水印区域
        watermark_region = img_array[y:y+watermark_h, x:x+watermark_w]

        # 简单inpainting: 使用周围区域的平均颜色填充
        # 扩展采样区域（水印上下边缘）
        border = 10
        if y > border and y + watermark_h + border < height:
            # 从上方取样
            top_sample = img_array[y-border:y, x:x+watermark_w]
            # 从下方取样
            bottom_sample = img_array[y+watermark_h:y+watermark_h+border, x:x+watermark_w]

            # 计算平均颜色（垂直方向的渐变填充）
            if len(top_sample) > 0 and len(bottom_sample) > 0:
                for i in range(watermark_h):
                    # 线性插值权重
                    alpha = i / watermark_h
                    # 上下区域平均
                    top_avg = np.mean(top_sample[min(i, len(top_sample)-1)], axis=0)
                    bottom_avg = np.mean(bottom_sample[min(i, len(bottom_sample)-1)], axis=0)
                    # 混合
                    fill_color = (1 - alpha) * top_avg + alpha * bottom_avg

                    # 填充到水印区域
                    img_array[y+i:y+i+1, x:x+watermark_w] = fill_color

        # 转回PIL图像
        result_img = Image.fromarray(img_array.astype(np.uint8))

        # 轻微模糊处理使填充更自然
        blurred_region = result_img.crop((x, y, x + watermark_w, y + watermark_h))
        blurred_region = blurred_region.filter(ImageFilter.SMOOTH)
        result_img.paste(blurred_region, (x, y))

        # 保存
        result_img.save(output_path, quality=95)
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
        print("方法: inpaint (默认, 智能修复) | crop (裁剪底部)")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    method = sys.argv[3] if len(sys.argv) > 3 else "inpaint"

    if not Path(input_path).exists():
        print(f"输入文件不存在: {input_path}")
        sys.exit(1)

    if method == "crop":
        success = remove_watermark_crop(input_path, output_path)
    else:
        success = remove_watermark_doubao(input_path, output_path)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
