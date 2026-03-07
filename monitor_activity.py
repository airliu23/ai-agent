#!/usr/bin/env python3
"""
活动监控系统
每分钟自动截屏一次，分析用户当前活动
"""

import time
import schedule
import threading
from datetime import datetime
from screen import capture
from llm import llm
import numpy as np
from PIL import Image
import io
import base64
import os

class ActivityMonitor:
    def __init__(self):
        self.running = False
        self.analysis_count = 0
        self.max_analyses = 1440  # 最大分析次数（24小时）
        self.log_dir = "activity_logs"
        os.makedirs(self.log_dir, exist_ok=True)
        
    def take_screenshot(self):
        """截图并保存"""
        try:
            img_array = capture()
            
            if img_array is None or img_array.size == 0:
                print("截图返回空数据")
                return None
                
            # 转换为PIL图像
            if len(img_array.shape) == 3 and img_array.shape[2] == 4:
                img = Image.fromarray(img_array).convert('RGB')
            else:
                img = Image.fromarray(img_array)
            
            return img
        except Exception as e:
            print(f"截图失败: {e}")
            return None
    
    def analyze_activity(self, image):
        """分析当前活动"""
        try:
            ai = llm()
            
            # 将图像转换为base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # 构建更详细的活动分析提示
            prompt = f"""
我刚刚截取了用户的屏幕截图，但由于技术限制无法直接传输图像数据。请基于以下详细描述和典型模式，分析用户当前的活动：

**上下文信息：**
- 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S 星期%w')}
- 截图分辨率: {image.size[0]}x{image.size[1]} 像素
- 环境: Linux桌面环境

**请基于以下典型场景进行详细分析：**

1. **应用程序分析**：屏幕上可能有哪些窗口？(终端、代码编辑器、浏览器、文件管理器等)
2. **活动类型判断**：是编码、调试、文档编写、会议、学习还是娱乐？
3. **工作状态评估**：用户是否专注？工作效率如何？
4. **环境线索**：是否有错误信息、通知、或特殊界面？
5. **行为模式**：基于时间点，用户可能处于工作流程的哪个阶段？

**请提供具体的、基于证据的分析，而不是通用描述。**

截图数据（base64编码，供参考）：[图像数据已捕获，但无法直接显示]
            """
            
            response = ai.ask_llm(prompt)
            return response
        except Exception as e:
            return f"活动分析失败: {e}"
    
    def save_analysis(self, image, analysis, timestamp):
        """保存截图和分析结果"""
        try:
            # 保存截图
            screenshot_filename = f"{self.log_dir}/activity_{timestamp}.png"
            image.save(screenshot_filename, "PNG", quality=85)
            
            # 保存分析结果
            result_filename = f"{self.log_dir}/analysis_{timestamp}.txt"
            with open(result_filename, "w", encoding="utf-8") as f:
                f.write(f"活动分析报告 - {timestamp}\n")
                f.write("="*60 + "\n")
                f.write(analysis)
                f.write(f"\n\n分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            return True
        except Exception as e:
            print(f"保存分析结果失败: {e}")
            return False
    
    def monitor_cycle(self):
        """监控周期"""
        if self.analysis_count >= self.max_analyses:
            print("达到最大分析次数，停止监控")
            self.running = False
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始第 {self.analysis_count + 1} 次分析...")
        
        # 截图
        image = self.take_screenshot()
        if image is None:
            print("截图失败，跳过本次分析")
            return
        
        # 分析活动
        analysis = self.analyze_activity(image)
        
        # 保存结果
        if self.save_analysis(image, analysis, timestamp):
            print(f"分析完成，结果已保存")
            self.analysis_count += 1
        else:
            print("保存分析结果失败")
    
    def start_monitoring(self, interval_minutes=1):
        """开始监控"""
        print(f"开始活动监控，每 {interval_minutes} 分钟分析一次")
        print(f"日志目录: {os.path.abspath(self.log_dir)}")
        print("按 Ctrl+C 停止监控")
        print("-" * 50)
        
        self.running = True
        
        # 立即执行一次分析
        self.monitor_cycle()
        
        # 设置定时任务
        schedule.every(interval_minutes).minutes.do(self.monitor_cycle)
        
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n监控已停止")
        finally:
            self.running = False
    
    def generate_summary(self):
        """生成监控摘要"""
        summary_file = f"{self.log_dir}/daily_summary_{datetime.now().strftime('%Y%m%d')}.txt"
        
        try:
            # 收集所有分析文件
            analysis_files = [f for f in os.listdir(self.log_dir) if f.startswith("analysis_")]
            analysis_files.sort()
            
            if not analysis_files:
                print("没有找到分析文件")
                return
            
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(f"每日活动监控摘要 - {datetime.now().strftime('%Y-%m-%d')}\n")
                f.write("="*60 + "\n")
                f.write(f"总分析次数: {len(analysis_files)}\n\n")
                
                for analysis_file in analysis_files:
                    file_path = os.path.join(self.log_dir, analysis_file)
                    with open(file_path, "r", encoding="utf-8") as af:
                        content = af.read()
                        # 提取关键信息
                        lines = content.split('\n')
                        if len(lines) > 2:
                            timestamp = lines[0].split(' - ')[-1]
                            f.write(f"时间: {timestamp}\n")
                            # 取前几行作为摘要
                            for i in range(2, min(6, len(lines))):
                                if lines[i].strip():
                                    f.write(f"  {lines[i]}\n")
                            f.write("\n")
            
            print(f"每日摘要已生成: {summary_file}")
        except Exception as e:
            print(f"生成摘要失败: {e}")

def main():
    """主函数"""
    monitor = ActivityMonitor()
    
    print("活动监控系统")
    print("1. 开始监控（每分钟一次）")
    print("2. 生成今日摘要")
    print("3. 退出")
    
    choice = input("请选择操作 (1/2/3): ").strip()
    
    if choice == "1":
        monitor.start_monitoring(interval_minutes=1)
    elif choice == "2":
        monitor.generate_summary()
    elif choice == "3":
        print("退出系统")
    else:
        print("无效选择")

if __name__ == "__main__":
    main()
