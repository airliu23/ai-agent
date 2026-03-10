# main.py - pywebview 浏览器内核版本
import webview
import threading
import queue
import time

from bug_record_core import BugRecord, BugToolUI

webview.settings['ALLOW_DOWNLOADS'] = True

class BrowserGUI(BugToolUI):
    """浏览器内核 GUI - 支持完美 Markdown 渲染"""
    
    def __init__(self):
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.window = None
        self.output_content = ""
        
        # 启动核心线程
        threading.Thread(target=self._run_core_loop, daemon=True).start()
        
        # 启动输出轮询线程
        threading.Thread(target=self._poll_output_loop, daemon=True).start()
        
        # 创建窗口
        self.window = webview.create_window(
            title='🐞 AI BUG 记录工具',
            url='gui.html',
            js_api=self,
            width=1200,
            height=800,
            min_size=(800, 600)
        )
    
    def receive_input(self, text):
        """JS 调用的方法，接收用户输入"""
        self.input_queue.put(text)
        return True
    
    def _run_core_loop(self):
        """核心业务逻辑线程"""
        tool = BugRecord(ui=self)
        while True:
            user_input = self.input_queue.get()
            try:
                tool.run(user_input)
            except Exception as e:
                self.output_queue.put(f"[错误] {e}\n")
    
    def _poll_output_loop(self):
        """输出轮询线程，定期将输出发送到前端"""
        while True:
            try:
                while True:
                    text = self.output_queue.get_nowait()
                    self.output_content += text + "\n"
                    # 调用 JS 更新显示
                    if self.window:
                        # 使用 JavaScript 调用 app.appendOutput
                        js_code = f'app.appendOutput({repr(text)})'
                        try:
                            self.window.evaluate_js(js_code)
                        except:
                            pass
            except queue.Empty:
                pass
            time.sleep(0.1)
    
    def log(self, text, end="\n"):
        """核心程序调用此方法输出"""
        print(text + end)
    
    def write(self, text):
        self.output_queue.put(text + "\n")
    
    def read(self, prompt="") -> str:
        """核心程序调用此方法获取输入（会阻塞核心线程）"""
        if (prompt != ""):
            self.output_queue.put(prompt + "\n")
        return self.input_queue.get()


def main():
    """程序入口"""
    gui = BrowserGUI()
    webview.start(gui="qt")


if __name__ == "__main__":
    main()