import mss
import numpy as np

def capture():

    with mss.mss() as sct:

        monitor = sct.monitors[1]
        img = sct.grab(monitor)

        return np.array(img)