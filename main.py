# main.py - pywebview 浏览器内核版本
import os
import webview
import threading
import queue
import time

from bug_record_core import BugRecord, BugToolUI
from llm import create_chat_session


def extract_pdf_content(file_path: str) -> str:
    """提取 PDF 文件的文本内容"""
    try:
        import PyPDF2
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text_parts = []
            for page_num, page in enumerate(pdf_reader.pages, 1):
                page_text = page.extract_text()
                if page_text.strip():
                    text_parts.append(f"--- 第 {page_num} 页 ---\n{page_text}")
            content = "\n\n".join(text_parts)
            return content if content.strip() else "[PDF 文件内容为空或无法提取文本]"
    except ImportError:
        return "[错误：未安装 PyPDF2 库，无法解析 PDF。请运行：pip install PyPDF2]"
    except Exception as e:
        return f"[PDF 解析错误：{str(e)}]"

webview.settings['ALLOW_DOWNLOADS'] = True

class BrowserGUI(BugToolUI):
    """浏览器内核 GUI - 支持完美 Markdown 渲染"""
    
    def __init__(self):
        self.input_queue = queue.Queue()
        self.output_queue = queue.Queue()
        self.window = None
        self.output_content = ""
        self.chat_session = create_chat_session(
            system_prompt="你是一个友好、简洁的中文聊天助手。",
            session_id="main_chat"
        )
        
        # 启动核心线程
        threading.Thread(target=self._run_core_loop, daemon=True).start()
        
        # 启动输出轮询线程
        threading.Thread(target=self._poll_output_loop, daemon=True).start()
        
        # 创建窗口
        self.window = webview.create_window(
            title='🐞 AI Agent',
            url='web/gui.html',
            js_api=self,
            width=1200,
            height=800,
            min_size=(800, 600)
        )
    
    def get_chat_history(self):
        """获取对话历史，用于前端恢复显示"""
        try:
            history = self.chat_session.get_chat_history()
            return {"success": True, "history": history}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def receive_input(self, text):
        """JS 调用的方法，接收 BUG 工具输入"""
        self.input_queue.put(text)
        return True

    def receive_chat(self, text):
        """JS 调用的方法，接收独立 AI 对话输入"""
        text = (text or "").strip()
        if not text:
            return {"success": False, "error": "输入不能为空"}

        try:
            reply = self.chat_session.send(text)
            return {"success": True, "reply": reply}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def clear_chat(self):
        """清空 AI 对话上下文并删除本地记录"""
        self.chat_session.reset()
        # 删除本地存储文件
        try:
            import os
            storage_file = self.chat_session.storage_file
            if os.path.exists(storage_file):
                os.remove(storage_file)
                print(f"[会话] 已删除本地记录: {storage_file}")
        except Exception as e:
            print(f"[会话] 删除本地记录失败: {e}")
        return {"success": True}

    def choose_chat_file(self):
        """为对话模式选择文件，并返回文件内容"""
        if not self.window:
            print("[DEBUG] 窗口未初始化")
            return {"success": False, "error": "窗口未初始化"}

        try:
            print("[DEBUG] 正在打开文件选择对话框...")
            
            # pywebview 文件对话框 - 不限制文件格式
            result = self.window.create_file_dialog(
                webview.OPEN_DIALOG, 
                allow_multiple=False
            )
            
            print(f"[DEBUG] 文件选择结果: {result}")

            if not result:
                print("[DEBUG] 用户取消选择或未选择文件")
                return {"success": False, "error": "未选择文件"}
            
            file_path = result[0] if isinstance(result, (list, tuple)) else result
            if not os.path.isfile(file_path):
                return {"success": False, "error": "文件不存在"}

            file_size = os.path.getsize(file_path)
            max_size = 1024 * 1024
            if file_size > max_size:
                return {"success": False, "error": f"文件过大（{file_size} 字节），请控制在 {max_size} 字节以内"}

            # 根据文件类型选择解析方式
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()

            if ext == ".pdf":
                content = extract_pdf_content(file_path)
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

            return {
                "success": True,
                "file_name": os.path.basename(file_path),
                "file_path": file_path,
                "content": content
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def receive_chat_file(self, question=""):
        """选择文件并直接发送给大模型分析"""
        print(f"[DEBUG] receive_chat_file 被调用，question={question}")
        file_result = self.choose_chat_file()
        print(f"[DEBUG] choose_chat_file 返回: {file_result.get('success')}")
        if not file_result.get("success"):
            return file_result

        question = (question or "").strip()
        prompt = (
            "请基于以下文件内容进行分析。\n\n"
            f"文件名：{file_result['file_name']}\n"
            f"文件路径：{file_result['file_path']}\n"
            "文件内容：\n"
            "```text\n"
            f"{file_result['content']}\n"
            "```\n\n"
        )

        if question:
            prompt += f"用户补充问题：{question}\n"
        else:
            prompt += "请先概括文件作用、主要结构、关键信息，并指出值得关注的问题。\n"

        try:
            reply = self.chat_session.send(prompt)
            return {
                "success": True,
                "reply": reply,
                "file_name": file_result["file_name"],
                "file_path": file_result["file_path"]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
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
        self.output_queue.put(text if end == "" else text + end.rstrip("\n"))
    
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
