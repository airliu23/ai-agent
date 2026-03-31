from abc import ABC, abstractmethod
import queue
import threading


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
    def write(self, text):
        print(text, flush=True)

    def read(self, prompt="") -> str:
        return input(prompt)
    
    def log(self, text, end="\n"):
        print(text, end=end, flush=True)


class BufferedUI(UI):
    """缓冲 UI，收集输出用于 API 返回"""
    
    def __init__(self):
        self._buffer = []
    
    def write(self, text):
        self._buffer.append(text)
    
    def read(self, prompt="") -> str:
        # API 模式不支持交互式输入，抛出异常以跳出循环
        raise InterruptedError("API 模式不支持交互式输入")
    
    def log(self, text, end="\n"):
        self._buffer.append(text)
    
    def get_output(self) -> str:
        """获取所有缓冲输出"""
        return "\n".join(self._buffer)
    
    def clear(self):
        """清空缓冲"""
        self._buffer = []


class QueueUI(UI):
    """队列驱动的 UI：write/log 直接输出，read 用队列阻塞等待"""
    
    def __init__(self):
        # 输入队列：API → 核心线程（解决阻塞读问题）
        self.input_queue = queue.Queue()
        # 输出缓冲：直接收集
        self._buffer = []
        # 等待输入标志
        self._waiting_input = False
        self._input_prompt = ""
    
    def write(self, text):
        """核心程序输出：直接收集到缓冲"""
        self._buffer.append(text)
    
    def read(self, prompt="") -> str:
        """核心程序输入：用队列阻塞等待"""
        if prompt:
            self._buffer.append(prompt)
        self._waiting_input = True
        self._input_prompt = prompt
        result = self.input_queue.get()  # 阻塞等待用户输入
        self._waiting_input = False
        return result
    
    def log(self, text, end="\n"):
        """核心程序日志：打印到后台，不在界面显示"""
        print(text, end=end, flush=True)
    
    # ===== API 调用的方法 =====
    
    def push_input(self, text: str):
        """推送用户输入到核心线程"""
        self.input_queue.put(text)
    
    def get_output(self) -> str:
        """获取并清空输出缓冲"""
        output = "\n".join(self._buffer)
        self._buffer = []
        return output
    
    def is_waiting_input(self) -> bool:
        """检查核心程序是否在等待输入"""
        return self._waiting_input
    
    def get_input_prompt(self) -> str:
        """获取当前输入提示"""
        return self._input_prompt
