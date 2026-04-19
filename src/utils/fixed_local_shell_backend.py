"""修复 Windows 编码问题和路径验证问题的 LocalShellBackend"""
import platform
import subprocess
from pathlib import Path

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import ExecuteResponse


class FixedLocalShellBackend(LocalShellBackend):
    """修复 Windows 下 subprocess 编码和路径验证问题的 Backend
    
    1. 重写 execute 方法，强制使用 UTF-8 编码解码子进程输出，
       避免 Windows 中文系统下 GBK 解码导致的 UnicodeDecodeError。
    2. 重写 _resolve_path 方法，处理 Windows 长路径前缀（\\?\）问题，
       确保虚拟路径验证时不会因为路径格式不一致导致失败。
    """

    def _resolve_path(self, key: str) -> Path:
        """重写父类方法，处理 Windows 长路径前缀问题
        
        Windows 上 Path.resolve() 可能返回带 \\?\ 前缀的路径，
        而 self.cwd 没有此前缀，导致 relative_to() 比较失败。
        此方法统一处理两种路径格式的比较。
        
        Args:
            key: 文件路径（绝对、相对或虚拟路径）
            
        Returns:
            解析后的绝对 Path 对象
            
        Raises:
            ValueError: 如果尝试路径遍历或路径超出 root_dir 范围
        """
        if self.virtual_mode:
            vpath = key if key.startswith("/") else "/" + key
            if ".." in vpath or vpath.startswith("~"):
                msg = "Path traversal not allowed"
                raise ValueError(msg)
            full = (self.cwd / vpath.lstrip("/")).resolve()
            
            # 处理 Windows 长路径前缀问题
            try:
                full.relative_to(self.cwd)
            except ValueError:
                # 可能是由于 \\?\ 前缀导致的比较失败
                full_str = str(full)
                cwd_str = str(self.cwd)
                
                # 如果 full 有 \\?\ 前缀而 cwd 没有，尝试规范化后再次比较
                if full_str.startswith("\\\\?\\") and not cwd_str.startswith("\\\\?\\"):
                    full_normalized = Path(full_str[4:])
                    try:
                        full_normalized.relative_to(self.cwd)
                        return full  # 验证通过，返回原始路径
                    except ValueError:
                        pass
                
                # 如果仍然失败，抛出原始错误
                msg = f"Path:{full} outside root directory: {self.cwd}"
                raise ValueError(msg) from None
            return full

        path = Path(key)
        if path.is_absolute():
            return path
        return (self.cwd / path).resolve()

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        """重写 execute 方法，强制使用 UTF-8 编码
        
        Args:
            command: 要执行的 shell 命令
            timeout: 超时时间（秒）
            
        Returns:
            ExecuteResponse: 包含命令执行结果
        """
        if not command or not isinstance(command, str):
            return ExecuteResponse(
                output="Error: Command must be a non-empty string.",
                exit_code=1,
                truncated=False,
            )

        effective_timeout = timeout if timeout is not None else self._default_timeout
        if effective_timeout <= 0:
            msg = f"timeout must be positive, got {effective_timeout}"
            raise ValueError(msg)

        try:
            # 在 Windows 上，先设置 CMD 代码页为 UTF-8，确保CMD对命令输出使用 UTF-8 编码
            if platform.system() == "Windows":
                # 使用 chcp 65001 将 CMD 代码页设置为 UTF-8
                command = f"chcp 65001 >nul && {command}"

            result = subprocess.run(
                command,
                check=False,
                shell=True,  # 启动一个shell进程执行command
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                env=self._env,
                cwd=str(self.cwd),
                encoding='utf-8',
                # 强制使用 UTF-8 解码command执行后的shell输出，即cmd等shell中运行命令（rm、dir、python、pytest）后输出的文字
                errors='replace',  # 遇到无法解码的字符用替换符代替，避免崩溃
            )

            # Combine stdout and stderr
            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout)
            if result.stderr:
                stderr_lines = result.stderr.strip().split("\n")
                output_parts.extend(f"[stderr] {line}" for line in stderr_lines)

            output = "\n".join(output_parts) if output_parts else "<no output>"

            # Check for truncation
            truncated = False
            if len(output) > self._max_output_bytes:
                output = output[: self._max_output_bytes]
                output += f"\n\n... Output truncated at {self._max_output_bytes} bytes."
                truncated = True

            # Add exit code info if non-zero
            if result.returncode != 0:
                output = f"{output.rstrip()}\n\nExit code: {result.returncode}"

            return ExecuteResponse(
                output=output,
                exit_code=result.returncode,
                truncated=truncated,
            )

        except subprocess.TimeoutExpired:
            if timeout is not None:
                msg = f"Error: Command timed out after {effective_timeout} seconds (custom timeout). The command may be stuck or require more time."
            else:
                msg = f"Error: Command timed out after {effective_timeout} seconds. For long-running commands, re-run using the timeout parameter."
            return ExecuteResponse(
                output=msg,
                exit_code=124,
                truncated=False,
            )
        except Exception as e:
            return ExecuteResponse(
                output=f"Error executing command ({type(e).__name__}): {e}",
                exit_code=1,
                truncated=False,
            )
