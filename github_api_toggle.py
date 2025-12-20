# github_api_toggle.py (или добавьте в существующий модуль)

def toggle_github_api_removal(parent, status_callback=None):
    """Переключает состояние удаления GitHub API из hosts"""
    from config import get_remove_github_api, set_remove_github_api
    from log import log
    
    try:
        current_state = get_remove_github_api()
        new_state = not current_state
        
        if set_remove_github_api(new_state):
            state_text = "включено" if new_state else "отключено"
            message = f"Удаление api.github.com из hosts {state_text}"
            log(message, "INFO")
            
            if status_callback:
                status_callback(message)
            return True
        else:
            error_msg = "Ошибка при сохранении настройки удаления GitHub API"
            log(error_msg, "❌ ERROR")
            if status_callback:
                status_callback(error_msg)
            return False
            
    except Exception as e:
        error_msg = f"Ошибка при переключении удаления GitHub API: {e}"
        log(error_msg, "❌ ERROR")
        if status_callback:
            status_callback(error_msg)
        return False