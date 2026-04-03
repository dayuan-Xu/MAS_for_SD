import subprocess
from rich.pretty import pprint


def windows_shell():
    """
    Test the Windows shell
    """
    cmd = "dir"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print("以下是shell命令执行结果")
    pprint(res)


windows_shell()