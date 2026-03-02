from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.settings import settings
from storage.repositories import AppSettingRepository


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("설정")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        desc = QLabel("전역 앱 설정(키워드/발행채널 설정은 각각 전용 메뉴에서 관리)")
        desc.setStyleSheet("color: #666;")
        root.addWidget(title)
        root.addWidget(desc)

        root.addWidget(self._build_app_box())
        root.addWidget(self._build_runtime_box())
        root.addStretch(1)
        self.setLayout(root)

    def _build_app_box(self) -> QGroupBox:
        box = QGroupBox("앱 정보")
        form = QFormLayout()

        self.app_name = QLineEdit(settings.app_name)
        self.app_name.setReadOnly(True)
        self.data_dir = QLineEdit(str(settings.data_dir))
        self.data_dir.setReadOnly(True)
        self.db_path = QLineEdit(str(settings.db_path))
        self.db_path.setReadOnly(True)

        form.addRow("앱 이름", self.app_name)
        form.addRow("데이터 경로", self.data_dir)
        form.addRow("DB 파일", self.db_path)
        box.setLayout(form)
        return box

    def _build_runtime_box(self) -> QGroupBox:
        box = QGroupBox("런타임 기본값")
        form = QFormLayout()

        self.max_collect = QSpinBox()
        self.max_collect.setRange(1, 100)
        self.max_collect.setValue(3)

        self.default_timeout = QSpinBox()
        self.default_timeout.setRange(1, 120)
        self.default_timeout.setValue(15)

        self.related_keyword_limit = QSpinBox()
        self.related_keyword_limit.setRange(5, 10)
        self.related_keyword_limit.setValue(10)

        save_btn = QPushButton("저장")
        save_btn.clicked.connect(self.save_settings)

        form.addRow("기본 수집 건수", self.max_collect)
        form.addRow("기본 타임아웃(초)", self.default_timeout)
        form.addRow("연관키워드 자동등록 상한", self.related_keyword_limit)
        form.addRow("", save_btn)
        box.setLayout(form)
        return box

    def refresh_all(self) -> None:
        self.related_keyword_limit.setValue(AppSettingRepository.get_related_keyword_limit(10))

    def save_settings(self) -> None:
        AppSettingRepository.set_related_keyword_limit(self.related_keyword_limit.value())
        QMessageBox.information(self, "저장", "설정이 저장되었습니다.")

