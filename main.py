# main.py - 简化版
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue

from bug_record_core import BugRecord, BugToolUI

class BugToolGUI(BugToolUI):
    """GUI 界面 - 使用线程隔离，不修改 core 代码"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🐞 AI BUG 记录工具")
        
        # 输入队列：GUI→核心线程
        self.input_queue = queue.Queue()
        # 输出队列：核心线程→GUI
        self.output_queue = queue.Queue()
        
        self._setup_ui()
        
        # 启动核心线程（运行原有的同步代码）
        threading.Thread(target=self._run_core_loop, daemon=True).start()
        
        # 定期处理输出队列
        self.root.after(100, self._poll_output)
    
    def _setup_ui(self):
        # 1. 输出文本区域
        self.text_area = scrolledtext.ScrolledText(self.root, state=tk.DISABLED)
        self.text_area.pack(fill=tk.BOTH, expand=True)
        
        # 2. 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 3. 输入区域
        input_frame = ttk.Frame(self.root)
        input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        self.entry = ttk.Entry(input_frame)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", self._on_submit)
        
        ttk.Button(input_frame, text="发送", command=self._on_submit).pack(side=tk.LEFT)
    
    def _on_submit(self, event=None):
        """提交输入到核心线程"""
        text = self.entry.get()
        self.entry.delete(0, tk.END)
        self._append_text(f"你：{text}\n")
        self.input_queue.put(text)  # 发送到核心线程
    
    def _run_core_loop(self):
        """核心线程：运行原有的同步代码"""
        tool = BugRecord(ui=self)
        
        while True:
            user_input = self.input_queue.get()  # 阻塞等待输入
            try:
                tool.run(user_input)  # 运行原有逻辑（阻塞在此）
            except Exception as e:
                self.output_queue.put(f"[错误] {e}\n")
    
    def _poll_output(self):
        """定期从队列取出输出并显示"""
        try:
            while True:
                text = self.output_queue.get_nowait()
                self._append_text(text)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_output)
    
    def _append_text(self, text: str):
        self.text_area.config(state=tk.NORMAL)
        self.text_area.insert(tk.END, text)
        self.text_area.see(tk.END)
        self.text_area.config(state=tk.DISABLED)
    
    # ========== 实现 UI 接口 ==========
    def log(self, text, end="\n"):
        """核心程序调用此方法输出"""
        self.output_queue.put(text + end)
    
    def write(self, text):
        self.output_queue.put(text)
    
    def read(self, prompt="") -> str:
        """核心程序调用此方法获取输入（会阻塞核心线程）"""
        self.output_queue.put(prompt)
        self.root.after(0, lambda: self.entry.config(state=tk.NORMAL))
        return self.input_queue.get()  # 阻塞等待用户输入


if __name__ == "__main__":
    root = tk.Tk()
    gui = BugToolGUI(root)
    root.mainloop()
