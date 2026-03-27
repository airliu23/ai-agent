const { app, BrowserWindow, ipcMain, dialog, Menu } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

// Linux 沙箱问题修复
if (process.platform === 'linux') {
    app.commandLine.appendSwitch('no-sandbox');
    app.commandLine.appendSwitch('disable-gpu-sandbox');
}

let mainWindow;
let pythonProcess;

// Python 后端服务器端口
const PYTHON_PORT = 5678;
const PYTHON_URL = `http://127.0.0.1:${PYTHON_PORT}`;

function createWindow() {
    // 隐藏顶部菜单栏
    Menu.setApplicationMenu(null);

    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        minWidth: 800,
        minHeight: 600,
        title: '🐞 AI Agent',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        }
    });

    // 开发模式加载 Vite 开发服务器，生产模式加载打包后的文件
    const isDev = process.argv.includes('--dev');
    if (isDev) {
        mainWindow.loadURL('http://localhost:5173');
        mainWindow.webContents.openDevTools();
    } else {
        mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

function startPythonBackend() {
    const pythonScript = path.join(__dirname, '../server.py');
    const venvPython = path.join(process.env.HOME, 'python-venv', 'bin', 'python3');
    const fs = require('fs');
    
    // 检查虚拟环境是否存在，使用虚拟环境的 Python
    const pythonPath = fs.existsSync(venvPython) ? venvPython : 'python3';
    console.log(`[Python] 使用 Python: ${pythonPath}`);
    
    // 启动 Python 后端
    pythonProcess = spawn(pythonPath, [pythonScript], {
        cwd: path.join(__dirname, '..'),
        env: { ...process.env, PYTHONUNBUFFERED: '1' }
    });

    pythonProcess.stdout.on('data', (data) => {
        console.log(`[Python] ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
        console.error(`[Python Error] ${data}`);
    });

    pythonProcess.on('close', (code) => {
        console.log(`[Python] 进程退出，退出码: ${code}`);
    });

    // 等待后端启动
    return new Promise((resolve) => {
        const checkServer = () => {
            fetch(PYTHON_URL + '/api/health')
                .then(() => resolve())
                .catch(() => setTimeout(checkServer, 500));
        };
        setTimeout(checkServer, 1000);
    });
}

function stopPythonBackend() {
    if (pythonProcess) {
        pythonProcess.kill();
        pythonProcess = null;
    }
}

// 处理文件选择对话框
ipcMain.handle('dialog:openFile', async () => {
    // 使用 mainWindow 作为父窗口，对话框关闭后焦点自然返回
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openFile'],
        filters: [
            { name: '所有文件', extensions: ['*'] }
        ]
    });
    return result.filePaths[0] || null;
});

// 应用启动
app.whenReady().then(async () => {
    console.log('正在启动 Python 后端...');
    await startPythonBackend();
    console.log('Python 后端已启动');
    
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

// 应用退出
app.on('window-all-closed', () => {
    stopPythonBackend();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('before-quit', () => {
    stopPythonBackend();
});
