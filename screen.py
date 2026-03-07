import mss
import numpy as np

def capture():
    """捕获主显示器截图"""
    with mss.mss() as sct:
        # 使用主显示器（索引0通常是主显示器）
        # monitors[0] 包含所有显示器的信息
        # monitors[1] 是第一个实际显示器
        if len(sct.monitors) > 1:
            # 使用主显示器
            monitor = sct.monitors[1]
        else:
            # 如果没有多个显示器，使用默认
            monitor = sct.monitors[0]
        
        print(f"捕获显示器: {monitor}")
        img = sct.grab(monitor)
        
        # 确保图像格式正确
        img_array = np.array(img)
        print(f"截图尺寸: {img_array.shape}")
        
        return img_array
