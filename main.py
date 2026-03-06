from llm import llm
from control import click, write, press, hotkey
from terminal_tool import run
import re

system_prompt = """
You are a Linux computer control agent.

You MUST reply with ONLY ONE action.

Allowed actions:

cmd:command
click x y
type text
press key
hotkey key1 key2

Rules:
1. Do not explain
2. Do not output markdown
3. Do not output multiple lines
4. Only output ONE action

Example:

Task: open chrome
cmd:google-chrome

Task: open douyin website
cmd:google-chrome https://www.douyin.com
"""

llm = llm()
while True:

    task = input("task> ")
    if (task == ""):
        continue

    prompt = system_prompt + "\nTask:" + task

    response = llm.ask_llm(prompt)

    match = re.search(r'(cmd:.*|click \d+ \d+|type .+|press \w+|hotkey .+)', response)

    if match:
        response = match.group(0)

    print("AI action:", response)

    if response.startswith("cmd:"):

        cmd = response.replace("cmd:", "")
        output = run(cmd)

        print(output)

    else:

        parts = response.split()

        if parts[0] == "click":
            click(int(parts[1]), int(parts[2]))

        elif parts[0] == "type":
            write(" ".join(parts[1:]))

        elif parts[0] == "press":
            press(parts[1])

        elif parts[0] == "hotkey":
            hotkey(*parts[1:])
