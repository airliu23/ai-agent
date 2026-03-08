from abc import ABC, abstractmethod
import queue
import threading
import time
import os
import select
import sys

class UI(ABC):
    """抽象用户界面接口"""
    @abstractmethod
    def write(self, text):
        """输出文本"""
        pass

    @abstractmethod
    def read(self, prompt="") -> str:
        """获取输入"""
        pass

    @abstractmethod
    def log(self, text):
        """输出文本"""
        pass

class TerminalUI(UI):
    """终端界面实现 - 支持push_input唤醒的同步输入"""
    def __init__(self):
        self.input_queue = queue.Queue()
    
    def write(self, text):
        print(text, flush=True)

    def read(self, prompt="") -> str:
        """同步输入函数 - 阻塞等待用户输入或队列中的输入"""
        if prompt:
            print(prompt, end="", flush=True)
        
        # 等待队列中有输入
        try:
            return self.input_queue.get()
        except queue.Empty:
            # 队列为空，返回空字符串（非阻塞）
            return ""
    
    def push_input(self, text):
        """外部推送输入到队列并唤醒阻塞的输入"""
        if text:
            self.input_queue.put(text)
    
    def has_input(self):
        """检查是否有待处理的输入"""
        return not self.input_queue.empty()
    
    def clear_input_queue(self):
        """清空输入队列"""
        while not self.input_queue.empty():
            try:
                self.input_queue.get_nowait()
            except queue.Empty:
                break
    
    def log(self, text):
        print(text, flush=True)
        