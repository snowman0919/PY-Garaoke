import os

def get_stylesheet():
    """
    Returns a modern Glassmorphism/Neumorphism inspired QSS stylesheet.
    """
    
    # Color Palette
    bg_color = "#2e2e3e"
    surface_color = "rgba(255, 255, 255, 0.08)" # Glassy effect
    text_color = "#ffffff"
    accent_color = "#6c5ce7" # Purple-ish
    accent_hover = "#a29bfe"
    border_color = "rgba(255, 255, 255, 0.2)"
    
    # Neumorphic/Glassmorphic styles (Simplified for Performance)
    style = f"""
    QMainWindow {{
        background-color: {bg_color};
        color: {text_color};
    }}
    
    QWidget {{
        background-color: {bg_color}; /* Solid background to reduce tearing */
        color: {text_color};
        font-family: 'Segoe UI', 'Roboto', sans-serif;
    }}

    /* Containers */
    QFrame, QListWidget, QTableWidget, QWidget#ResultsWidget {{
        background-color: #34344a; /* Solid color slightly lighter than bg */
        border: 1px solid {border_color};
        border-radius: 15px;
    }}
    
    /* Singing Widget needs to be clean for high FPS updates */
    QWidget#SingingWidget {{
        background-color: {bg_color};
        border: none;
    }}
    
    /* PitchVisualizationWidget handles its own painting */
    QWidget#PitchVisualizationWidget {{
        background: transparent;
        border: none;
    }}

    /* Buttons */
    QPushButton {{
        background-color: #3f3f5f; /* Solid hex instead of rgba */
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 10px 20px;
        color: white;
        font-weight: bold;
        font-size: 14px;
    }}
    
    QPushButton:hover {{
        background-color: {accent_color};
        border-color: {accent_hover};
    }}
    
    QPushButton:pressed {{
        background-color: #4834d4;
        padding-top: 12px; 
        padding-left: 22px;
    }}

    /* Inputs */
    QLineEdit {{
        background-color: #1e1e2e; /* Solid dark */
        border: 1px solid {border_color};
        border-radius: 8px;
        padding: 8px;
        color: white;
        font-size: 14px;
    }}
    
    QLineEdit:focus {{
        border: 1px solid {accent_color};
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        border: none;
        background: #2e2e3e;
        width: 10px;
        margin: 0px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background: #5e5e7e;
        min-height: 20px;
        border-radius: 5px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* Table Widget */
    QTableWidget {{
        gridline-color: transparent;
        selection-background-color: {accent_color};
        selection-color: white;
        outline: none;
        background-color: #34344a;
    }}
    QHeaderView::section {{
        background-color: #3f3f5f;
        color: white;
        padding: 5px;
        border: none;
        border-bottom: 1px solid {border_color};
        font-weight: bold;
    }}
    
    /* Specific Widgets */
    QLabel#ScoreLabel {{
        color: {accent_hover};
        font-weight: 800;
        background-color: transparent;
    }}
    
    QLabel#LyricsLabel {{
        color: #dfe6e9;
        font-weight: 600;
        background-color: transparent;
    }}

    QProgressBar {{
        border: 1px solid {border_color};
        border-radius: 5px;
        text-align: center;
        background-color: #1e1e2e;
    }}
    QProgressBar::chunk {{
        background-color: {accent_color};
        border-radius: 4px;
    }}
    """
    return style

def apply_theme(app_or_widget):
    app_or_widget.setStyleSheet(get_stylesheet())

def load_fonts():
    # Placeholder for font loading
    pass