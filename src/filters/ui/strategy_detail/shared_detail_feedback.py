from __future__ import annotations


def apply_detail_loading_indicator(
    spinner,
    success_icon,
    *,
    loading: bool = False,
    success: bool = False,
    success_pixmap=None,
) -> None:
    if loading:
        try:
            success_icon.hide()
        except Exception:
            pass
        try:
            spinner.show()
        except Exception:
            pass
        try:
            spinner.start()
        except Exception:
            pass
        return

    try:
        spinner.stop()
    except Exception:
        pass
    try:
        spinner.hide()
    except Exception:
        pass

    if success:
        try:
            if success_pixmap is not None:
                success_icon.setPixmap(success_pixmap)
        except Exception:
            pass
        try:
            success_icon.show()
        except Exception:
            pass
        return

    try:
        success_icon.hide()
    except Exception:
        pass
