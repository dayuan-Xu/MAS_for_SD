import os

from src.config.settings import settings


def settings_load_openai_api_key():
    """测试 Settings 能正确加载 OPENAI_API_KEY"""
    print("\nsettings.OPENAI_API_KEY:", settings.CHATANYWHERE_OPENAI_API_KEY)
    assert settings.CHATANYWHERE_OPENAI_API_KEY != "", "OPENAI_API_KEY 应该在 .env 文件中有定义！"


def settings_not_in_os_environ():
    """测试 Settings只是会从.env中读取的值，而不会把其中定义的任何变量注入到环境变量
    比如这里的OPENAI_API_KEY虽然被Settings读入到settings这个对象中，但是并不在系统环境变量中
    但是LANGSMITH_ENDPOINT由于被手动加载，所以在系统变量中"""
    print("\nsettings.OPENAI_API_KEY:", settings.CHATANYWHERE_OPENAI_API_KEY)
    print("\nos.getenv('OPENAI_API_KEY'):", os.getenv('OPENAI_API_KEY'))
    print("\nos.getenv('LANGSMITH_ENDPOINT'):", os.getenv('LANGSMITH_ENDPOINT'))


# 测试系统环境变量和dot env中同名变量哪个优先级更高
def settings_env_file_lower_than_system_env():
    """测试 系统环境变量的优先级高于.env 文件中定义的值"""
    print("\nos.getenv('MY_VAR'):", os.getenv('JAVA_HOME'))
    print("\nsettings.JAVA_HOME:", settings.JAVA_HOME)


settings_not_in_os_environ()
