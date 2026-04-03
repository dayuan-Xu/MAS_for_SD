import os
from rich.pretty import pprint

"""
Windows 环境变量的两种类型
1. 系统变量（System Variables）
    作用范围：对所有用户都生效
    存储位置：注册表 HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Session Manager\Environment
    权限要求：需要管理员权限才能修改
    使用场景：全局配置，如 JAVA_HOME、PYTHON_HOME 等
2. 用户变量（User Variables）
    作用范围：仅对当前登录用户生效
    存储位置：注册表 HKEY_CURRENT_USER\Environment
    权限要求：不需要管理员权限
    使用场景：个人专属配置
"""

# 访问操作系统的环境变量,既包括系统变量，也包括用户变量
# os.environ 只能访问已加载到当前进程的环境变量，无法直接区分是系统变量还是用户变量
pprint(os.environ)