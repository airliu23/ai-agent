#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BUG记录工具 - GUI 完整版
完美兼容修复后的core代码，支持闲聊、指令、BUG记录全功能
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import sys
import os

# 导入核心模块
sys.path.append(os.path.dirname(__file__))
from bug_record_core import BugDialogTool, BugToolUI

class TextRedirector:
    """标准输出/错误重定向器，用于劫持print输出"""
    def __init__(self, text_widget, tag: str = "stdout"):
        self.text_widget = text_widget
        self.tag = tag

    def write(self, text: str):
        if text.strip():
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, text, (self.tag,))
            self.text_widget.see(tk.END)
            self.text_widget.config(state=tk.DISABLED)

    def flush(self):
        pass

class BugToolGUI(BugToolUI):
    """GUI界面实现，完全兼容BugToolUI接口"""
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🐞 AI BUG 记录工具")
        self.root.geometry("1000x700")
        self.root.minsize(800, 500)

        # 线程安全队列：用于输入请求和结果传递
        self.result_queue = queue.Queue()
        self.input_prompt = ""

        # 构建UI界面
        self._setup_ui()

        # 保存原始标准流
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

    def _setup_ui(self):
        """构建UI界面"""
        # 全局字体配置
        default_font = ("Microsoft YaHei", 10)
        code_font = ("Consolas", 10)

        # 1. 顶部标题栏
        top_bar = ttk.Frame(self.root, padding="10 5 10 5")
        top_bar.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(top_bar, text="AI BUG 记录工具", font=("Microsoft YaHei", 14, "bold")).pack(side=tk.LEFT)

        # 2. 输出文本区域
        log_frame = ttk.LabelFrame(self.root, text="程序输出", padding="10")
        log_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.text_area = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, font=code_font, state=tk.DISABLED
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)

        # 配置文本颜色标签
        self.text_area.tag_config("stdout", foreground="black")
        self.text_area.tag_config("stderr", foreground="red")
        self.text_area.tag_config("input", foreground="#0066cc", font=(code_font[0], code_font[1], "bold"))

        # 3. 底部输入区域
        input_frame = ttk.Frame(self.root, padding="10")
        input_frame.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Label(input_frame, text="输入:", font=default_font).pack(side=tk.LEFT, padx=5)

        self.entry = ttk.Entry(input_frame, font=default_font)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.entry.bind("<Return>", self._on_submit)

        self.send_btn = ttk.Button(input_frame, text="发送", command=self._on_submit)
        self.send_btn.pack(side=tk.LEFT, padx=5)

        # 初始禁用输入，等待核心程序请求
        self._set_input_enabled(False)

    def _set_input_enabled(self, enabled: bool):
        """设置输入框状态"""
        if enabled:
            self.entry.config(state=tk.NORMAL)
            self.send_btn.config(state=tk.NORMAL)
            self.entry.focus_set()
        else:
            self.entry.config(state=tk.DISABLED)
            self.send_btn.config(state=tk.DISABLED)

    def _on_submit(self, event=None):
        """提交输入内容"""
        user_text = self.entry.get()
        self.entry.delete(0, tk.END)

        # 回显输入内容
        self._append_text(f"{user_text}\n", "input")

        # 禁用输入
        self._set_input_enabled(False)

        # 将结果放入队列，传递给等待的核心线程
        try:
            self.result_queue.put(user_text, block=False)
        except queue.Full:
            pass

    def _append_text(self, text: str, tag: str = "stdout"):
        """向文本区域追加内容"""
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, text, (tag,))
        self.text_area.see(tk.END)
        self.text_area.config(state=tk.DISABLED)

    # ------------------- 实现BugToolUI接口 -------------------
    def output(self, text: str):
        """核心程序调用的输出方法"""
        self._append_text(text, "stdout")

    def input(self, prompt: str = "") -> str:
        """核心程序调用的输入方法（会阻塞子线程）"""
        # 显示提示语
        if prompt:
            self._append_text(prompt, "stdout")
        
        # 在主线程激活输入框
        self.root.after(0, lambda: self._set_input_enabled(True))
        
        # 阻塞等待用户输入（子线程中运行，不影响GUI）
        return self.result_queue.get()

def main():
    """GUI程序入口"""
    root = tk.Tk()
    gui = BugToolGUI(root)

    # 劫持标准输出和错误输出，所有print都会显示在GUI中
    sys.stdout = TextRedirector(gui.text_area, "stdout")
    sys.stderr = TextRedirector(gui.text_area, "stderr")

    # 核心业务逻辑线程（避免阻塞GUI主循环）
    def run_core_logic():
        try:
            # 实例化工具，传入GUI作为UI
            tool = BugDialogTool(ui=gui)
            # 直接运行核心主循环
            tool.run()
        except Exception as e:
            print(f"\n[系统错误] 程序运行异常: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    # 启动核心线程
    threading.Thread(target=run_core_logic, daemon=True).start()

    # 启动GUI主循环
    root.mainloop()

if __name__ == "__main__":
    main()