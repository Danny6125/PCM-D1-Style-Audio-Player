# core/utils.py


def format_time(ms: int) -> str:
    if ms is None or ms < 0:
        ms = 0
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"
