---
name: python-full-stack-development
description: Use this skill when you are working on Python project development.
license: MIT
compatibility: None
metadata:
  author: boss
  version: "1.0"
---

# Python 全栈开发技能

## 概述

本技能提供 Python 项目开发的完整指导，包括虚拟环境创建、依赖管理、使用国内镜像源加速包安装等最佳实践。

## 使用说明

### 1. 创建 Python 虚拟环境

在开始任何 Python 项目之前，**必须**创建独立的虚拟环境以避免依赖冲突。

#### 推荐使用 venv创建项目虚拟环境

```bash
# 在项目根目录执行，以创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
# Linux/macOS:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

### 2. 使用国内镜像源

为避免从 PyPI 官方源下载时的超时问题，**必须**使用国内镜像源。

#### 单次安装直接使用-i参数（安装前确保激活项目虚拟环境）

```bash

# 清华大学镜像（推荐优先使用）
pip install <package_name> -i https://pypi.tuna.tsinghua.edu.cn/simple

```


### 3. 安装项目依赖

#### 从 requirements.txt 安装（若当前python项目已有requirements.txt）

```bash
# 使用国内镜像源安装所有依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 若已永久配置国内镜像源，直接运行
pip install -r requirements.txt
```

#### 生成 requirements.txt

```bash
# 导出当前环境的依赖
pip freeze > requirements.txt

# 或使用 pipreqs 只导出项目实际使用的依赖
pip install pipreqs
pipreqs ./ --encoding=utf-8 --force
```


### 4. 常见问题与解决方案

#### 问题 1：pip install 超时

**症状：**
```
ERROR: Could not find a version that satisfies the requirement xxx
ERROR: No matching distribution found for xxx
```

**解决方案：**
```bash
# 使用镜像源并增加超时时间
pip install <package> -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300
```

#### 问题 2：SSL 证书错误

**症状：**
```
SSLError: HTTPSConnectionPool(host='pypi.org', port=443): Max retries exceeded
```

**解决方案：**
```bash
# 使用可信主机参数
pip install <package> -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
```

#### 问题 3：依赖冲突

**症状：**
```
ERROR: Cannot install xxx and yyy because these package versions have conflicting dependencies.
```

**解决方案：**
```bash
# 使用 pip-tools 解决依赖冲突
pip install pip-tools
pip-compile requirements.in  # 生成锁定的 requirements.txt
pip-sync requirements.txt    # 同步安装
```

#### 问题 4：虚拟环境未激活

**症状：**
安装包后无法导入，或者安装到了系统 Python 而非虚拟环境。

**解决方案：**
```bash
# 检查当前 Python 路径
which python  # Linux/macOS
where python  # Windows

# 确保路径包含 .venv
# 例如：/path/to/project/.venv/bin/python

# 如果未激活，重新激活
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
```

### 7. 最佳实践

#### ✅ 推荐做法

1. **每个项目都使用独立的虚拟环境**
   ```bash
   cd /path/to/project
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **在国内开发 Python 项目时，始终使用国内镜像源**
   - 优先使用清华镜像：`https://pypi.tuna.tsinghua.edu.cn/simple`
   - 备选镜像：
     -  中国科技大学镜像：https://pypi.mirrors.ustc.edu.cn/simple
     -  阿里云镜像：https://mirrors.aliyun.com/pypi/simple/
     -  豆瓣镜像：https://pypi.douban.com/simple

3. **项目完成后锁定依赖版本，方便他人复现**
   ```bash
   # 使用精确版本号
   pip freeze > requirements.txt
   
   # 或在 requirements.txt 中指定
   flask==3.0.0
   requests>=2.28.0,<3.0.0
   ```
4. **编写高质量代码**
- 变量命名清晰有意义
- 关键逻辑添加注释
- 适当的错误处理
- 避免硬编码，使用常量或配置

5. **使用模快方式运行代码**
- 避免运行代码时直接使用脚本文件路径，而是使用模块方式运行，即python -m 模块路径

#### ❌ 避免的做法

1. **不要使用 `sudo pip install`** - 会污染系统 Python
2. **不要在全局环境安装项目依赖** - 使用虚拟环境
3. **不要忽略 requirements.txt** - 确保项目可复现
4. **不要从官方源直接下载大Package** - 使用国内镜像