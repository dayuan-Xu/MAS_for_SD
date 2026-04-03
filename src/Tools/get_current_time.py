from langchain_core.tools import tool


@tool
def get_current_time():
    """
    Returns the current time as a string in the format "YYYY-MM-DD HH:MM:SS".
    """
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")