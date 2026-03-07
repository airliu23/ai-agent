import subprocess
import signal
import os

def run(cmd, timeout=30):
    """
    执行命令，添加超时机制
    :param cmd: 要执行的命令
    :param timeout: 超时时间（秒），默认30秒
    :return: 命令输出或错误信息
    """
    try:
        # 使用Popen而不是run，以便更好地控制超时
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid  # 创建新的进程组
        )
        
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            return stdout + stderr
        except subprocess.TimeoutExpired:
            # 超时时终止整个进程组
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            return f"命令执行超时（{timeout}秒）"
            
    except Exception as e:
        return f"命令执行错误: {str(e)}"
