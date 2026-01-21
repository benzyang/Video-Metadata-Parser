# 使用脚本所在目录作为基准
$BaseDir = $PSScriptRoot

# 定义 Python 路径
$PythonExe = "D:\Miniconda3\envs\yang\python.exe"

# 执行命令
& $PythonExe "$BaseDir\parsex.py" -i "E:\qBittorrent\Downloads\newp" -c "$BaseDir\csv\p.csv"