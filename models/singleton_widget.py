# singleton_widget.py
from models.singleton_meta import SingletonMeta, QWidget  # re‑exported for convenience
   
class SingletonWidget(QWidget, metaclass=SingletonMeta):
    """
    A QWidget that is automatically a singleton.

    Subclass this when you want a global UI component (e.g. a settings dialog,
    a custom toolbar, a plot canvas, …).  No extra code is required.
    """
    pass
