import sys
import re
import signal
import time
from llm import llm
from control import click, write, press, hotkey
from terminal_tool import run

# 信号处理函数，用于优雅退出
def signal_handler(sig, frame):
    print("\n程序已退出")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

system_prompt = ""
try:
    with open('prompt.txt', 'r', encoding='utf-8') as file:
        system_prompt = file.read()
    print(system_prompt)
except Exception as e:
    print(f"读取提示文件失败: {e}")
    sys.exit(1)

llm = llm()
print("AI控制代理已启动，输入 'exit' 或 'quit' 退出程序")
print("输入 Ctrl+C 也可以退出程序")

while True:
    try:
        task = input("task> ").strip()
        
        # 退出机制
        if task.lower() in ['exit', 'quit']:
            print("退出程序")
            break
        if task == "":
            continue

        prompt = system_prompt + "\nTask:" + task
        print("正在处理任务...")

        # 添加超时机制
        response = llm.ask_llm(prompt)
        
        if isinstance(response, dict) and 'error' in response:
            print(f"AI请求错误: {response['error']}")
            continue

        match = re.search(r'(cmd:.*|click \d+ \d+|type .+|press \w+|hotkey .+)', response)

        if match:
            response = match.group(0)
        else:
            print(f"无法解析AI响应: {response}")
            continue

        print("AI action:", response)

        if response.startswith("cmd:"):
            cmd = response.replace("cmd:", "").strip()
            print(f"执行命令: {cmd}")
            
            try:
                output = run(cmd)
                if output:
                    print(f"命令输出: {output}")
            except Exception as e:
                print(f"命令执行失败: {e}")

        else:
            parts = response.split()
            if len(parts) < 2:
                print("无效的操作格式")
                continue

            try:
                if parts[0] == "click":
                    if len(parts) >= 3:
                        click(int(parts[1]), int(parts[2]))
                        print(f"点击位置: ({parts[1]}, {parts[2]})")
                    else:
                        print("点击操作需要x和y坐标")

                elif parts[0] == "type":
                    text = " ".join(parts[1:])
                    write(text)
                    print(f"输入文本: {text}")

                elif parts[0] == "press":
                    press(parts[1])
                    print(f"按下按键: {parts[1]}")

                elif parts[0] == "hotkey":
                    if len(parts) >= 2:
                        hotkey(*parts[1:])
                        print(f"组合键: {'+'.join(parts[1:])}")
                    else:
                        print("组合键操作需要至少一个按键")

                else:
                    print(f"未知操作: {parts[0]}")

            except Exception as e:
                print(f"操作执行失败: {e}")

    except KeyboardInterrupt:
        print("\n程序被用户中断")
        break
    except Exception as e:
        print(f"发生未知错误: {e}")
        continue

print("程序结束")
