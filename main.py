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
        # 创建 PanedWindow 容器（支持垂直拖放调整比例）
        self.paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        self.paned.pack(fill=tk.BOTH, expand=True)
        
        # ===== 上框架：输出显示区域 =====
        top_frame = ttk.Frame(self.paned)
        self.text_area = scrolledtext.ScrolledText(
            top_frame, 
            state=tk.DISABLED,
            wrap=tk.WORD,
            font=("Consolas", 10)
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)
        self.paned.add(top_frame, weight=3)  # 上半部分权重为 3
        
        # ===== 状态栏 =====
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # ===== 下框架：多行输入区域 + 发送按钮 =====
        bottom_frame = ttk.Frame(self.paned)
        
        # 多行输入框
        self.input_text = scrolledtext.ScrolledText(
            bottom_frame, 
            height=6,           # 初始高度 6 行
            wrap=tk.WORD,       # 自动换行
            font=("Consolas", 10)
        )
        self.input_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.input_text.bind("<Control-Return>", self._on_submit)  # Ctrl+Enter 发送
        
        # 按钮区域（垂直排列在右侧）
        btn_frame = ttk.Frame(bottom_frame)
        ttk.Button(btn_frame, text="发送", command=self._on_submit).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="清空", command=self._clear_input).pack(fill=tk.X, pady=2)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        self.paned.add(bottom_frame, weight=1)  # 下半部分权重为 1
    
    def _on_submit(self, event=None):
        """提交输入到核心线程"""
        text = self.input_text.get("1.0", tk.END).strip()
        if not text:
            return
        
        # 在文本末尾添加 ### 标记
        text_with_marker = text
        
        self.input_text.delete("1.0", tk.END)
        self._append_text(f"你：{text_with_marker}\n")
        self.input_queue.put(text_with_marker)  # 发送到核心线程
    
    def _clear_input(self):
        """清空输入框"""
        self.input_text.delete("1.0", tk.END)
    
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
        print(text + end)
    
    def write(self, text):
        self.output_queue.put(text + "\n")
    
    def read(self, prompt="") -> str:
        """核心程序调用此方法获取输入（会阻塞核心线程）"""
        self.output_queue.put(prompt + "\n")
        self.root.after(0, lambda: None)  # 空操作，保持 GUI 响应
        return self.input_queue.get()  # 阻塞等待用户输入


if __name__ == "__main__":
    root = tk.Tk()
    gui = BugToolGUI(root)
    root.mainloop()