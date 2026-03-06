import pyautogui

pyautogui.FAILSAFE = True

def click(x, y):
    pyautogui.click(x, y)

def write(text):
    pyautogui.write(text)

def press(key):
    pyautogui.press(key)

def hotkey(*keys):
    pyautogui.hotkey(*keys)