from abc import ABC, abstractmethod


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
        