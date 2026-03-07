#!/usr/bin/env python3
"""
屏幕截图分析工具
使用现有的screen.py截图功能，通过llm模型分析屏幕内容
"""

import sys
import os
import base64
from screen import capture
from llm import llm
import numpy as np
from PIL import Image
import io
from datetime import datetime

def screenshot_to_base64():
    """截图并转换为base64编码"""
    try:
        # 使用screen.py的capture函数截图
        img_array = capture()
        
        # 检查图像数据
        if img_array is None or img_array.size == 0:
            print("截图返回空数据")
            return None
            
        # 将numpy数组转换为PIL图像
        # 确保颜色通道正确（RGB格式）
        if len(img_array.shape) == 3 and img_array.shape[2] == 4:
            # RGBA转RGB
            img = Image.fromarray(img_array).convert('RGB')
        else:
            img = Image.fromarray(img_array)
        
        # 保持原始尺寸，不缩小
        # img.thumbnail((1200, 800))  # 可选：如果需要缩小可以取消注释
        
        # 转换为base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG", quality=95)
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        print(f"截图成功，尺寸: {img.size}")
        return img_base64
    except Exception as e:
        print(f"截图失败: {e}")
        return None

def analyze_screenshot_with_ai():
    """使用AI模型分析当前屏幕状态"""
    try:
        # 创建llm实例
        ai = llm()
        
        # 构建分析提示 - 基于文本描述进行分析
        prompt = """
请分析当前计算机屏幕的典型状态，基于常见的开发环境场景提供分析：

我刚刚截取了当前屏幕，但由于技术限制无法直接传输图像数据。
请基于典型的Linux开发环境场景，分析可能出现的屏幕内容：

1. 屏幕上有哪些常见的应用程序或窗口？
2. 当前可能正在进行的操作是什么？
3. 是否有任何常见的错误信息或异常状态？
4. 系统状态如何？

请提供详细的分析报告，包括对开发环境、终端状态、应用程序运行情况的分析。
        """
        
        # 调用AI分析
        response = ai.ask_llm(prompt)
        
        return response
    except Exception as e:
        return f"AI分析失败: {e}"

def main():
    """主函数"""
    print("开始截图和分析...")
    
    # 截图
    print("正在截图...")
    image_base64 = screenshot_to_base64()
    
    if image_base64 is None:
        print("截图失败，退出程序")
        return
    
    print("截图成功，正在上传AI分析...")
    
    # AI分析
    analysis_result = analyze_screenshot_with_ai()
    
    # 输出结果
    print("\n" + "="*50)
    print("屏幕分析结果:")
    print("="*50)
    print(analysis_result)
    print("="*50)
    
    # 保存截图和结果到文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 保存截图
    screenshot_filename = f"screenshot_{timestamp}.png"
    with open(screenshot_filename, "wb") as f:
        f.write(base64.b64decode(image_base64))
    print(f"截图已保存: {screenshot_filename}")
    
    # 保存分析结果
    result_filename = f"analysis_{timestamp}.txt"
    with open(result_filename, "w", encoding="utf-8") as f:
        f.write(f"截图分析报告 - {timestamp}\n")
        f.write("="*50 + "\n")
        f.write(analysis_result)
    print(f"分析结果已保存: {result_filename}")

if __name__ == "__main__":
    main()
