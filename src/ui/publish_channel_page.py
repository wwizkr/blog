from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from storage.repositories import PublishChannelRepository, PublishChannelSettingRepository


class PublishChannelPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("발행채널 관리")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        root.addWidget(self._build_channel_box())
        root.addWidget(self._build_channel_setting_box(), 1)

        self.setLayout(root)

    def _build_channel_box(self) -> QGroupBox:
        box = QGroupBox("채널 등록/활성화")
        layout = QVBoxLayout()

        row = QHBoxLayout()
        self.channel_code_input = QLineEdit()
        self.channel_code_input.setPlaceholderText("채널 코드 (예: wp_api)")
        self.channel_name_input = QLineEdit()
        self.channel_name_input.setPlaceholderText("채널명 (예: 워드프레스 API)")
        add_btn = QPushButton("발행채널 추가")
        add_btn.clicked.connect(self.add_publish_channel)
        toggle_btn = QPushButton("선택 채널 활성/비활성")
        toggle_btn.clicked.connect(self.toggle_publish_channel)
        row.addWidget(self.channel_code_input)
        row.addWidget(self.channel_name_input)
        row.addWidget(add_btn)
        row.addWidget(toggle_btn)
        row.addStretch(1)

        self.channel_table = QTableWidget(0, 4)
        self.channel_table.setHorizontalHeaderLabels(["ID", "코드", "채널명", "활성"])
        self.channel_table.verticalHeader().setVisible(False)
        self.channel_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.channel_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.channel_table.setColumnWidth(0, 60)
        self.channel_table.setColumnWidth(1, 150)
        self.channel_table.setColumnWidth(3, 70)
        self.channel_table.horizontalHeader().setStretchLastSection(True)

        layout.addLayout(row)
        layout.addWidget(self.channel_table)
        box.setLayout(layout)
        return box

    def _build_channel_setting_box(self) -> QGroupBox:
        box = QGroupBox("채널별 발행 설정")
        layout = QVBoxLayout()

        self.publish_table = QTableWidget(0, 7)
        self.publish_table.setHorizontalHeaderLabels(["채널", "주기(분)", "모드", "발행형식", "작성형식", "API URL", "ID"])
        self.publish_table.verticalHeader().setVisible(False)
        self.publish_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.publish_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.publish_table.setColumnWidth(0, 140)
        self.publish_table.setColumnWidth(1, 90)
        self.publish_table.setColumnWidth(2, 90)
        self.publish_table.setColumnWidth(3, 90)
        self.publish_table.setColumnWidth(4, 90)
        self.publish_table.setColumnWidth(5, 240)
        self.publish_table.setColumnHidden(6, True)
        self.publish_table.horizontalHeader().setStretchLastSection(True)
        self.publish_table.itemSelectionChanged.connect(self._fill_publish_form_from_selection)
        layout.addWidget(self.publish_table)

        form_row = QHBoxLayout()
        self.publish_channel = QComboBox()
        self.publish_api_url = QLineEdit()
        self.publish_api_url.setPlaceholderText("https://api.example.com/publish")
        self.publish_cycle = QSpinBox()
        self.publish_cycle.setRange(5, 1440)
        self.publish_cycle.setValue(60)
        self.publish_mode = QComboBox()
        self.publish_mode.addItem("반자동", "semi_auto")
        self.publish_mode.addItem("자동", "auto")
        self.publish_format = QComboBox()
        self.publish_format.addItem("블로그", "blog")
        self.publish_format.addItem("SNS", "sns")
        self.publish_format.addItem("게시판", "board")
        self.writing_style = QComboBox()
        self.writing_style.addItem("정보형", "informative")
        self.writing_style.addItem("감성형", "emotional")
        self.writing_style.addItem("후기형", "review")

        save_btn = QPushButton("설정 저장")
        save_btn.clicked.connect(self.save_publish_setting)

        form_row.addWidget(QLabel("채널"))
        form_row.addWidget(self.publish_channel)
        form_row.addWidget(QLabel("API URL"))
        form_row.addWidget(self.publish_api_url)
        form_row.addWidget(QLabel("주기(분)"))
        form_row.addWidget(self.publish_cycle)
        form_row.addWidget(QLabel("모드"))
        form_row.addWidget(self.publish_mode)
        form_row.addWidget(QLabel("발행형식"))
        form_row.addWidget(self.publish_format)
        form_row.addWidget(QLabel("작성형식"))
        form_row.addWidget(self.writing_style)
        form_row.addWidget(save_btn)
        form_row.addStretch(1)
        layout.addLayout(form_row)

        box.setLayout(layout)
        return box

    def refresh_all(self) -> None:
        channels = PublishChannelRepository.list_all()
        PublishChannelSettingRepository.ensure_for_channels([row.code for row in channels])
        self.refresh_channels()
        self.refresh_publish_settings()

    def refresh_channels(self) -> None:
        rows = PublishChannelRepository.list_all()
        self.channel_table.setRowCount(len(rows))
        for i, item in enumerate(rows):
            self.channel_table.setItem(i, 0, QTableWidgetItem(str(item.id)))
            self.channel_table.setItem(i, 1, QTableWidgetItem(item.code))
            self.channel_table.setItem(i, 2, QTableWidgetItem(item.display_name))
            self.channel_table.setItem(i, 3, QTableWidgetItem("Y" if item.is_enabled else "N"))

    def refresh_publish_settings(self) -> None:
        channel_rows = PublishChannelRepository.list_all()
        rows = PublishChannelSettingRepository.list_all()
        self.publish_table.setRowCount(len(rows))
        self.publish_channel.clear()
        for channel in channel_rows:
            label = f"{channel.display_name} ({channel.code})"
            if not channel.is_enabled:
                label += " [비활성]"
            self.publish_channel.addItem(label, channel.code)
        for row, item in enumerate(rows):
            self.publish_table.setItem(row, 0, QTableWidgetItem(item.channel_code))
            self.publish_table.setItem(row, 1, QTableWidgetItem(str(item.publish_cycle_minutes)))
            self.publish_table.setItem(row, 2, QTableWidgetItem(item.publish_mode))
            self.publish_table.setItem(row, 3, QTableWidgetItem(item.publish_format))
            self.publish_table.setItem(row, 4, QTableWidgetItem(item.writing_style))
            self.publish_table.setItem(row, 5, QTableWidgetItem(item.api_url or ""))
            self.publish_table.setItem(row, 6, QTableWidgetItem(str(item.id)))

    def _fill_publish_form_from_selection(self) -> None:
        row = self.publish_table.currentRow()
        if row < 0:
            return
        channel = self.publish_table.item(row, 0).text()
        cycle = int(self.publish_table.item(row, 1).text())
        mode = self.publish_table.item(row, 2).text()
        fmt = self.publish_table.item(row, 3).text()
        style = self.publish_table.item(row, 4).text()

        idx = self.publish_channel.findData(channel)
        if idx >= 0:
            self.publish_channel.setCurrentIndex(idx)
        self.publish_cycle.setValue(cycle)
        self._select_combo_by_data(self.publish_mode, mode)
        self._select_combo_by_data(self.publish_format, fmt)
        self._select_combo_by_data(self.writing_style, style)
        setting = PublishChannelSettingRepository.get_by_channel(channel)
        self.publish_api_url.setText(setting.api_url if setting and setting.api_url else "")

    def _select_combo_by_data(self, combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _selected_channel_id(self) -> int | None:
        row = self.channel_table.currentRow()
        if row < 0:
            return None
        item = self.channel_table.item(row, 0)
        return int(item.text()) if item else None

    def add_publish_channel(self) -> None:
        code = self.channel_code_input.text().strip()
        name = self.channel_name_input.text().strip()
        if not PublishChannelRepository.add(code=code, display_name=name):
            QMessageBox.warning(self, "알림", "발행채널 추가 실패 (빈 값/중복 코드)")
            return
        PublishChannelSettingRepository.ensure_for_channels([code])
        self.channel_code_input.clear()
        self.channel_name_input.clear()
        self.refresh_all()
        QMessageBox.information(self, "추가", "발행채널이 추가되었습니다.")

    def toggle_publish_channel(self) -> None:
        channel_id = self._selected_channel_id()
        if channel_id is None:
            QMessageBox.information(self, "알림", "발행채널을 선택하세요.")
            return
        PublishChannelRepository.toggle(channel_id)
        self.refresh_all()

    def save_publish_setting(self) -> None:
        channel_code = self.publish_channel.currentData()
        if not channel_code:
            QMessageBox.warning(self, "알림", "채널을 선택하세요.")
            return
        PublishChannelSettingRepository.upsert(
            channel_code=channel_code,
            publish_cycle_minutes=self.publish_cycle.value(),
            publish_mode=self.publish_mode.currentData(),
            publish_format=self.publish_format.currentData(),
            writing_style=self.writing_style.currentData(),
            api_url=self.publish_api_url.text().strip(),
        )
        self.refresh_publish_settings()
        QMessageBox.information(self, "저장", "발행 채널 설정이 저장되었습니다.")

