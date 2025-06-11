# test_gui.py
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout

app = QApplication(sys.argv)

window = QWidget()
window.setWindowTitle('센서 GUI 예시')
layout = QVBoxLayout()

label = QLabel('온도: 25.0°C\n습도: 60.0%\n릴레이 상태: OFF')
layout.addWidget(label)

window.setLayout(layout)
window.show()

sys.exit(app.exec_())
