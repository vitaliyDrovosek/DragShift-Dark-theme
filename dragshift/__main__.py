import sys
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

# --- ГЛОБАЛЬНЫЙ ПЕРЕХВАТЧИК PAINT EVENT ---
# Мы оборачиваем оригинальный paintEvent всех виджетов.
# Даже если внутри произойдет ошибка, мы принудительно вызовем end().

_original_paint = QWidget.paintEvent

def _safe_paint(self, event):
    # Создаем "страховочный" QPainter. 
    # Если оригинальный код создаст свой, этот просто закроется.
    p_guard = QPainter(self)
    try:
        _original_paint(self, event)
    finally:
        # Принудительно закрываем все активные painter'ы у этого виджета
        for obj in [p_guard]:
            try:
                if obj.isActive():
                    obj.end()
            except Exception:
                pass

QWidget.paintEvent = _safe_paint
# --- КОНЕЦ ПЕРЕХВАТЧИКА ---

if __name__ == "__main__":
    from dragshift.app import main
    sys.exit(main())