"""测试 process_command_parts 函数。

该函数用于在复合命令中的每个 python/python3 子命令前添加 PYTHONUTF8=1 环境变量。
"""
import pytest

from src.utils.common import process_command_parts


class TestProcessCommandParts:
    """process_command_parts 函数的测试用例"""

    def test_simple_python_command(self):
        """测试简单的 Python 命令"""
        cmd = 'python3 -c "print(\'hello\')"'
        result = process_command_parts(cmd)
        assert result == 'PYTHONUTF8=1 python3 -c "print(\'hello\')"'

    def test_simple_python_command_without_version(self):
        """测试不带版本号的 python 命令"""
        cmd = 'python script.py'
        result = process_command_parts(cmd)
        assert result == 'PYTHONUTF8=1 python script.py'

    def test_cd_and_python(self):
        """测试 cd && python 复合命令（你提到的情况）"""
        cmd = 'cd /tmp/... && python3 -c "XXX"'
        result = process_command_parts(cmd)
        # PYTHONUTF8=1 应该只添加到 python3 前面，而不是 cd 前面
        assert result == 'cd /tmp/... && PYTHONUTF8=1 python3 -c "XXX"'

    def test_multiple_python_commands(self):
        """测试多个 Python 命令"""
        cmd = 'echo "test" && python3 script.py && python3 -c "code"'
        result = process_command_parts(cmd)
        # 两个 python 命令都应该添加环境变量
        assert 'PYTHONUTF8=1 python3 script.py' in result
        assert 'PYTHONUTF8=1 python3 -c "code"' in result
        # echo 命令不应该有环境变量
        assert result.startswith('echo "test" &&')

    def test_already_has_utf8_env(self):
        """测试已经有 PYTHONUTF8=1 的命令，不应重复添加"""
        cmd = 'PYTHONUTF8=1 python3 -c "code"'
        result = process_command_parts(cmd)
        # 不应该重复添加
        assert result == 'PYTHONUTF8=1 python3 -c "code"'
        # 确保只有一个 PYTHONUTF8=1
        assert result.count('PYTHONUTF8=1') == 1

    def test_non_python_command(self):
        """测试非 Python 命令，不应添加环境变量"""
        cmd = 'ls -la /tmp'
        result = process_command_parts(cmd)
        assert result == 'ls -la /tmp'
        assert 'PYTHONUTF8=1' not in result

    def test_mixed_commands(self):
        """测试混合命令：包含 Python 和非 Python 命令"""
        cmd = 'mkdir -p /tmp/test && cd /tmp/test && python3 main.py'
        result = process_command_parts(cmd)
        # 只有 python3 命令应该有环境变量
        assert 'mkdir -p /tmp/test && cd /tmp/test && PYTHONUTF8=1 python3 main.py' == result

    def test_semicolon_separator(self):
        """测试使用分号分隔的命令"""
        cmd = 'cd /tmp; python3 test.py'
        result = process_command_parts(cmd)
        assert result == 'cd /tmp; PYTHONUTF8=1 python3 test.py'

    def test_pipe_separator(self):
        """测试使用管道符分隔的命令"""
        cmd = 'cat file.txt | python3 process.py'
        result = process_command_parts(cmd)
        # cat 不应该有环境变量，python3 应该有
        assert result == 'cat file.txt | PYTHONUTF8=1 python3 process.py'

    def test_or_separator(self):
        """测试使用 || 分隔的命令"""
        cmd = 'command1 || python3 fallback.py'
        result = process_command_parts(cmd)
        assert result == 'command1 || PYTHONUTF8=1 python3 fallback.py'

    def test_complex_compound_command(self):
        """测试复杂的复合命令"""
        cmd = 'cd /workspace && mkdir -p output && python3 main.py --config test.json && echo "Done"'
        result = process_command_parts(cmd)
        # 只有 python3 命令应该有环境变量
        expected = 'cd /workspace && mkdir -p output && PYTHONUTF8=1 python3 main.py --config test.json && echo "Done"'
        assert result == expected

    def test_preserve_leading_spaces(self):
        """测试保留前导空格"""
        cmd = '  python3 script.py'
        result = process_command_parts(cmd)
        # 应该保留前导空格
        assert result == '  PYTHONUTF8=1 python3 script.py'

    def test_case_insensitive_python(self):
        """测试大小写不敏感的 python 匹配"""
        cmd = 'Python3 script.py'
        result = process_command_parts(cmd)
        assert result == 'PYTHONUTF8=1 Python3 script.py'

    def test_python_in_middle_of_word_not_matched(self):
        """测试 python 作为单词一部分时不应匹配"""
        # ipython 不应该被匹配为 python
        cmd = 'ipython notebook'
        result = process_command_parts(cmd)
        # ipython 不是 python，所以不应该添加环境变量
        assert result == 'ipython notebook'
        assert 'PYTHONUTF8=1' not in result

    def test_empty_command(self):
        """测试空命令"""
        cmd = ''
        result = process_command_parts(cmd)
        assert result == ''

    def test_only_spaces(self):
        """测试只有空格的命令"""
        cmd = '   '
        result = process_command_parts(cmd)
        assert result == '   '

    def test_python_with_arguments(self):
        """测试带参数的 Python 命令"""
        cmd = 'python3 -m pytest tests/ -v --tb=short'
        result = process_command_parts(cmd)
        assert result == 'PYTHONUTF8=1 python3 -m pytest tests/ -v --tb=short'

    def test_multiple_separators(self):
        """测试多个分隔符的情况"""
        cmd = 'cmd1 && cmd2 || python3 script.py ; cmd4'
        result = process_command_parts(cmd)
        assert 'PYTHONUTF8=1 python3 script.py' in result

    def test_python_at_beginning(self):
        """测试 Python 命令在开头"""
        cmd = 'python3 run.py && echo "finished"'
        result = process_command_parts(cmd)
        assert result.startswith('PYTHONUTF8=1 python3 run.py')

    def test_python_at_end(self):
        """测试 Python 命令在结尾"""
        cmd = 'setup.sh && python3 app.py'
        result = process_command_parts(cmd)
        assert result.endswith('PYTHONUTF8=1 python3 app.py')

    def test_real_world_example_1(self):
        """真实场景示例 1：读取文件的 Python 命令"""
        # 这是 BaseSandbox.read() 生成的典型命令
        cmd = '''python3 -c "
import os, sys, base64, json
path = '/tmp/test.txt'
with open(path, 'r') as f:
    print(f.read())
"'''
        result = process_command_parts(cmd)
        assert result.startswith('PYTHONUTF8=1 python3 -c "')

    def test_real_world_example_2(self):
        """真实场景示例 2：带 cd 的复合命令"""
        cmd = 'cd /workspace/project && python3 -c "import sys; print(sys.version)"'
        result = process_command_parts(cmd)
        assert 'cd /workspace/project && PYTHONUTF8=1 python3 -c "' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
