#!/usr/bin/env python3
"""
视频录制模块
使用 OpenCV 和 mss 库实现屏幕视频录制功能
"""

import cv2
import numpy as np
import mss
import time
import os
from datetime import datetime
import threading
from PIL import Image

class VideoRecorder:
    def __init__(self, output_dir="video_recordings", fps=15, quality=85):
        """
        初始化视频录制器
        
        Args:
            output_dir: 输出目录
            fps: 帧率
            quality: 视频质量 (0-100)
        """
        self.output_dir = output_dir
        self.fps = fps
        self.quality = quality
        self.recording = False
        self.video_writer = None
        self.recording_thread = None
        self.frame_count = 0
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
    def get_screen_resolution(self):
        """获取屏幕分辨率"""
        with mss.mss() as sct:
            if len(sct.monitors) > 1:
                monitor = sct.monitors[1]  # 主显示器
            else:
                monitor = sct.monitors[0]  # 默认显示器
            return monitor['width'], monitor['height']
    
    def capture_frame(self):
        """捕获一帧屏幕"""
        try:
            with mss.mss() as sct:
                if len(sct.monitors) > 1:
                    monitor = sct.monitors[1]
                else:
                    monitor = sct.monitors[0]
                
                # 捕获屏幕
                screenshot = sct.grab(monitor)
                
                # 转换为numpy数组
                frame = np.array(screenshot)
                
                # 转换颜色空间 BGR to RGB
                if len(frame.shape) == 3 and frame.shape[2] == 4:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                elif len(frame.shape) == 3 and frame.shape[2] == 3:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                return frame
        except Exception as e:
            print(f"捕获帧失败: {e}")
            return None
    
    def start_recording(self, filename=None, duration=None):
        """
        开始录制视频
        
        Args:
            filename: 输出文件名（可选，自动生成时间戳）
            duration: 录制时长（秒，可选，无限录制）
        """
        if self.recording:
            print("已经在录制中")
            return False
        
        # 生成文件名
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.mp4"
        
        filepath = os.path.join(self.output_dir, filename)
        
        # 获取屏幕分辨率
        width, height = self.get_screen_resolution()
        print(f"屏幕分辨率: {width}x{height}")
        
        # 创建视频编码器
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_writer = cv2.VideoWriter(
            filepath, 
            fourcc, 
            self.fps, 
            (width, height)
        )
        
        if not self.video_writer.isOpened():
            print("无法创建视频文件")
            return False
        
        self.recording = True
        self.frame_count = 0
        self.duration = duration
        self.start_time = time.time()
        
        # 启动录制线程
        self.recording_thread = threading.Thread(target=self._recording_loop)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        
        print(f"开始录制视频: {filepath}")
        print(f"帧率: {self.fps} fps")
        if duration:
            print(f"录制时长: {duration} 秒")
        else:
            print("录制时长: 无限")
        
        return True
    
    def _recording_loop(self):
        """录制循环"""
        frame_interval = 1.0 / self.fps
        
        while self.recording:
            start_frame_time = time.time()
            
            # 检查录制时长
            if self.duration and (time.time() - self.start_time) >= self.duration:
                print("达到录制时长，停止录制")
                self.stop_recording()
                break
            
            # 捕获帧
            frame = self.capture_frame()
            if frame is not None:
                # 写入视频
                self.video_writer.write(frame)
                self.frame_count += 1
                
                # 显示录制状态
                if self.frame_count % (self.fps * 5) == 0:  # 每5秒显示一次
                    elapsed = time.time() - self.start_time
                    print(f"已录制: {elapsed:.1f}秒, 帧数: {self.frame_count}")
            
            # 控制帧率
            elapsed_frame_time = time.time() - start_frame_time
            sleep_time = max(0, frame_interval - elapsed_frame_time)
            time.sleep(sleep_time)
    
    def stop_recording(self):
        """停止录制"""
        if not self.recording:
            print("当前没有在录制")
            return
        
        self.recording = False
        
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)
        
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
        
        elapsed = time.time() - self.start_time
        print(f"录制已停止")
        print(f"总时长: {elapsed:.1f}秒")
        print(f"总帧数: {self.frame_count}")
        print(f"实际帧率: {self.frame_count/elapsed:.1f} fps")
    
    def pause_recording(self):
        """暂停录制（需要手动实现状态管理）"""
        print("暂停功能需要手动实现状态管理")
        # 可以扩展实现暂停/继续功能
    
    def get_recording_status(self):
        """获取录制状态"""
        if self.recording:
            elapsed = time.time() - self.start_time
            return {
                'recording': True,
                'elapsed_time': elapsed,
                'frame_count': self.frame_count,
                'current_fps': self.frame_count / elapsed if elapsed > 0 else 0
            }
        else:
            return {'recording': False}

def record_screen(duration=None, fps=15, output_dir="video_recordings"):
    """
    快速录制屏幕的便捷函数
    
    Args:
        duration: 录制时长（秒）
        fps: 帧率
        output_dir: 输出目录
    """
    recorder = VideoRecorder(output_dir=output_dir, fps=fps)
    
    print("准备开始录制...")
    print("按 Ctrl+C 停止录制")
    
    try:
        recorder.start_recording(duration=duration)
        
        if duration:
            # 如果指定了时长，等待录制完成
            time.sleep(duration)
            recorder.stop_recording()
        else:
            # 无限录制，等待用户中断
            while recorder.recording:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\n用户中断录制")
        recorder.stop_recording()
    except Exception as e:
        print(f"录制出错: {e}")
        recorder.stop_recording()

def main():
    """主函数 - 命令行界面"""
    import argparse
    
    parser = argparse.ArgumentParser(description="屏幕视频录制工具")
    parser.add_argument("-d", "--duration", type=int, help="录制时长（秒）")
    parser.add_argument("-f", "--fps", type=int, default=15, help="帧率（默认15）")
    parser.add_argument("-o", "--output", default="video_recordings", help="输出目录")
    
    args = parser.parse_args()
    
    print("屏幕视频录制工具")
    print("=" * 40)
    
    if args.duration:
        print(f"将录制 {args.duration} 秒视频")
    else:
        print("将无限录制（按 Ctrl+C 停止）")
    
    record_screen(duration=args.duration, fps=args.fps, output_dir=args.output)

if __name__ == "__main__":
    main()
