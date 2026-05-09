"""测试 UnicodeDecodeInterceptor 功能"""
from langchain_core.messages import ToolMessage
from mcp.types import TextContent, CallToolResult

from src.utils.mcp_interceptors import UnicodeDecodeInterceptor


def test_call_tool_result_decode():
    """测试 CallToolResult 解码"""
    print('测试1: CallToolResult 解码')

    interceptor = UnicodeDecodeInterceptor()

    # 创建包含 Unicode 转义字符的测试结果
    test_result = CallToolResult(
        content=[TextContent(type='text', text="button with text \\u767e\\u5ea6\\u4e00\\u4e0b at index [436]")],
        isError=False
    )

    decoded = interceptor._decode_call_tool_result(test_result)

    print(f'原始文本: {test_result.content[0].text}')
    print(f'解码后: {decoded.content[0].text}')
    print(f'预期结果: button with text 百度一下 at index [436]')
    print()

    assert decoded.content[0].text == "button with text 百度一下 at index [436]", "解码失败"
    print('✓ 测试通过\n')


def test_tool_message_decode():
    """测试 ToolMessage 解码"""
    print('测试2: ToolMessage 解码')

    interceptor = UnicodeDecodeInterceptor()

    # 创建包含 Unicode 转义字符的测试消息
    test_message = ToolMessage(
        content="placeholder \\u6d4f\\u9633\\u70df\\u82b1\\u5382\\u4e8b\\u6545",
        tool_call_id='test_123'
    )

    decoded_msg = interceptor._decode_tool_message(test_message)

    print(f'原始文本: {test_message.content}')
    print(f'解码后: {decoded_msg.content}')
    print(f'预期结果: placeholder 浏阳烟花厂事故')
    print()

    assert decoded_msg.content == "placeholder 浏阳烟花厂事故", "解码失败"
    print('✓ 测试通过\n')


def test_tool_message_list_decode():
    """测试 ToolMessage 列表内容解码"""
    print('测试3: ToolMessage 列表内容解码')

    interceptor = UnicodeDecodeInterceptor()

    # 创建包含多个字符串的列表
    test_message = ToolMessage(
        content=[
            r'元素1: \u6d4b\u8bd5',
            '元素2: 正常文本',
            r'元素3: \u767e\u5ea6'
        ],
        tool_call_id='test_456'
    )

    decoded_msg = interceptor._decode_tool_message(test_message)

    print(f'原始文本: {test_message.content}')
    print(f'解码后: {decoded_msg.content}')
    print()

    assert decoded_msg.content[0] == '元素1: 测试', "第一个元素解码失败"
    assert decoded_msg.content[1] == '元素2: 正常文本', "第二个元素被错误修改"
    assert decoded_msg.content[2] == '元素3: 百度', "第三个元素解码失败"
    print('✓ 测试通过\n')


def test_no_unicode_text():
    """测试不含 Unicode 的文本"""
    print('测试4: 不含 Unicode 的文本')

    interceptor = UnicodeDecodeInterceptor()

    test_result = CallToolResult(
        content=[TextContent(type='text', text='This is normal text without unicode')],
        isError=False
    )

    decoded = interceptor._decode_call_tool_result(test_result)

    print(f'原始文本: {test_result.content[0].text}')
    print(f'解码后: {decoded.content[0].text}')
    print()

    assert decoded.content[0].text == test_result.content[0].text, "无 Unicode 文本被错误修改"
    print('✓ 测试通过\n')


if __name__ == '__main__':
    print('=' * 80)
    print('UnicodeDecodeInterceptor 功能测试')
    print('=' * 80)
    print()

    try:
        test_call_tool_result_decode()
        test_tool_message_decode()
        test_tool_message_list_decode()
        test_no_unicode_text()

        print('=' * 80)
        print('所有测试通过！✓')
        print('=' * 80)
    except AssertionError as e:
        print(f'测试失败: {e}')
        exit(1)
    except Exception as e:
        print(f'发生错误: {e}')
        import traceback

        traceback.print_exc()
        exit(1)
