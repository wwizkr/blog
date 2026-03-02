from __future__ import annotations

from sqlalchemy import select

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from storage.database import session_scope
from storage.models import ContentLabel, ImageLabel, RawContent, RawImage
from storage.repositories import LabelRepository


class CollectedDataPage(QWidget):
    def __init__(self):
        super().__init__()
        self._content_rows: list[dict] = []
        self._image_rows: list[dict] = []
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("수집 데이터 / 라벨 검수")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_content_tab(), "수집 텍스트")
        self.tabs.addTab(self._build_image_tab(), "수집 이미지")
        root.addWidget(self.tabs, 1)

        refresh_btn = QPushButton("새로고침")
        refresh_btn.clicked.connect(self.refresh_all)
        root.addWidget(refresh_btn)

        self.setLayout(root)

    def _build_content_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()

        self.content_table = QTableWidget(0, 4)
        self.content_table.setHorizontalHeaderLabels(["ID", "키워드", "채널", "제목"])
        self.content_table.verticalHeader().setVisible(False)
        self.content_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.content_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.content_table.setColumnWidth(0, 60)
        self.content_table.setColumnWidth(1, 120)
        self.content_table.setColumnWidth(2, 100)
        self.content_table.horizontalHeader().setStretchLastSection(True)
        self.content_table.itemSelectionChanged.connect(self.on_select_content)
        layout.addWidget(self.content_table)

        self.source_url = QLineEdit()
        self.source_url.setReadOnly(True)
        self.body_text = QTextEdit()
        self.body_text.setReadOnly(True)
        self.body_text.setMaximumHeight(220)

        layout.addWidget(QLabel("원문 URL"))
        layout.addWidget(self.source_url)
        layout.addWidget(QLabel("원문 본문"))
        layout.addWidget(self.body_text)

        content_label_box = QGroupBox("텍스트 라벨 수정")
        content_label_form = QFormLayout()
        self.tone_input = QLineEdit()
        self.sentiment_input = QLineEdit()
        self.topics_input = QLineEdit()
        self.topics_input.setPlaceholderText("예: 여행,맛집,후기")
        self.content_quality = QSpinBox()
        self.content_quality.setRange(1, 5)
        self.content_quality.setValue(3)
        save_content_label_btn = QPushButton("텍스트 라벨 저장")
        save_content_label_btn.clicked.connect(self.save_content_label)
        content_label_form.addRow("톤", self.tone_input)
        content_label_form.addRow("감성", self.sentiment_input)
        content_label_form.addRow("주제", self.topics_input)
        content_label_form.addRow("품질점수", self.content_quality)
        content_label_form.addRow("", save_content_label_btn)
        content_label_box.setLayout(content_label_form)
        layout.addWidget(content_label_box)

        page.setLayout(layout)
        return page

    def _build_image_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()

        self.image_table = QTableWidget(0, 4)
        self.image_table.setHorizontalHeaderLabels(["ID", "content_id", "이미지 URL", "로컬경로"])
        self.image_table.verticalHeader().setVisible(False)
        self.image_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.image_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.image_table.setColumnWidth(0, 60)
        self.image_table.setColumnWidth(1, 90)
        self.image_table.setColumnWidth(2, 360)
        self.image_table.horizontalHeader().setStretchLastSection(True)
        self.image_table.itemSelectionChanged.connect(self.on_select_image)
        layout.addWidget(self.image_table)

        self.image_url_view = QLineEdit()
        self.image_url_view.setReadOnly(True)
        layout.addWidget(QLabel("선택 이미지 URL"))
        layout.addWidget(self.image_url_view)

        image_label_box = QGroupBox("이미지 라벨 수정")
        image_label_form = QFormLayout()
        self.image_category_input = QLineEdit()
        self.image_mood_input = QLineEdit()
        self.image_quality = QSpinBox()
        self.image_quality.setRange(1, 5)
        self.image_quality.setValue(3)
        self.image_thumb = QCheckBox("썸네일 후보")
        save_image_label_btn = QPushButton("이미지 라벨 저장")
        save_image_label_btn.clicked.connect(self.save_image_label)
        image_label_form.addRow("카테고리", self.image_category_input)
        image_label_form.addRow("분위기", self.image_mood_input)
        image_label_form.addRow("품질점수", self.image_quality)
        image_label_form.addRow("", self.image_thumb)
        image_label_form.addRow("", save_image_label_btn)
        image_label_box.setLayout(image_label_form)
        layout.addWidget(image_label_box)

        page.setLayout(layout)
        return page

    def refresh_all(self) -> None:
        self._load_contents()
        self._load_images()
        self.source_url.clear()
        self.body_text.clear()
        self.image_url_view.clear()

    def _load_contents(self) -> None:
        with session_scope() as session:
            rows = session.execute(select(RawContent).order_by(RawContent.created_at.desc()).limit(200)).scalars().all()
            self._content_rows = [
                {
                    "id": row.id,
                    "keyword": row.keyword.keyword if row.keyword else "-",
                    "channel": row.channel_code,
                    "title": row.title,
                    "source_url": row.source_url,
                    "body_text": row.body_text,
                }
                for row in rows
            ]

        self.content_table.setRowCount(len(self._content_rows))
        for i, item in enumerate(self._content_rows):
            self.content_table.setItem(i, 0, QTableWidgetItem(str(item["id"])))
            self.content_table.setItem(i, 1, QTableWidgetItem(item["keyword"]))
            self.content_table.setItem(i, 2, QTableWidgetItem(item["channel"]))
            self.content_table.setItem(i, 3, QTableWidgetItem(item["title"]))

    def _load_images(self) -> None:
        with session_scope() as session:
            rows = session.execute(select(RawImage).order_by(RawImage.created_at.desc()).limit(400)).scalars().all()
            self._image_rows = [
                {
                    "id": row.id,
                    "content_id": row.content_id,
                    "image_url": row.image_url,
                    "local_path": row.local_path or "",
                }
                for row in rows
            ]

        self.image_table.setRowCount(len(self._image_rows))
        for i, item in enumerate(self._image_rows):
            self.image_table.setItem(i, 0, QTableWidgetItem(str(item["id"])))
            self.image_table.setItem(i, 1, QTableWidgetItem(str(item["content_id"])))
            self.image_table.setItem(i, 2, QTableWidgetItem(item["image_url"]))
            self.image_table.setItem(i, 3, QTableWidgetItem(item["local_path"]))

    def _selected_content_id(self) -> int | None:
        row = self.content_table.currentRow()
        if row < 0:
            return None
        item = self.content_table.item(row, 0)
        return int(item.text()) if item else None

    def _selected_image_id(self) -> int | None:
        row = self.image_table.currentRow()
        if row < 0:
            return None
        item = self.image_table.item(row, 0)
        return int(item.text()) if item else None

    def on_select_content(self) -> None:
        content_id = self._selected_content_id()
        if content_id is None:
            return
        selected = next((row for row in self._content_rows if row["id"] == content_id), None)
        if not selected:
            return
        self.source_url.setText(selected["source_url"])
        self.body_text.setPlainText(selected["body_text"])

        with session_scope() as session:
            label = session.execute(select(ContentLabel).where(ContentLabel.content_id == content_id)).scalar_one_or_none()
            self.tone_input.setText(label.tone if label and label.tone else "")
            self.sentiment_input.setText(label.sentiment if label and label.sentiment else "")
            if label and label.topics:
                try:
                    import json

                    topics = json.loads(label.topics)
                    self.topics_input.setText(",".join(topics) if isinstance(topics, list) else "")
                except Exception:
                    self.topics_input.setText("")
            else:
                self.topics_input.setText("")
            self.content_quality.setValue(label.quality_score if label else 3)

    def on_select_image(self) -> None:
        image_id = self._selected_image_id()
        if image_id is None:
            return
        selected = next((row for row in self._image_rows if row["id"] == image_id), None)
        if not selected:
            return
        self.image_url_view.setText(selected["image_url"])

        with session_scope() as session:
            label = session.execute(select(ImageLabel).where(ImageLabel.image_id == image_id)).scalar_one_or_none()
            self.image_category_input.setText(label.category if label and label.category else "")
            self.image_mood_input.setText(label.mood if label and label.mood else "")
            self.image_quality.setValue(label.quality_score if label else 3)
            self.image_thumb.setChecked(bool(label.is_thumbnail_candidate) if label else False)

    def save_content_label(self) -> None:
        content_id = self._selected_content_id()
        if content_id is None:
            QMessageBox.information(self, "알림", "텍스트 라벨을 저장할 수집 글을 선택하세요.")
            return
        topics = [item.strip() for item in self.topics_input.text().split(",") if item.strip()]
        LabelRepository.upsert_content_label(
            content_id=content_id,
            tone=self.tone_input.text().strip() or None,
            sentiment=self.sentiment_input.text().strip() or None,
            topics=topics,
            quality_score=self.content_quality.value(),
        )
        QMessageBox.information(self, "저장", "텍스트 라벨이 저장되었습니다.")

    def save_image_label(self) -> None:
        image_id = self._selected_image_id()
        if image_id is None:
            QMessageBox.information(self, "알림", "이미지 라벨을 저장할 이미지를 선택하세요.")
            return
        LabelRepository.upsert_image_label(
            image_id=image_id,
            category=self.image_category_input.text().strip() or None,
            mood=self.image_mood_input.text().strip() or None,
            quality_score=self.image_quality.value(),
            is_thumbnail_candidate=self.image_thumb.isChecked(),
        )
        QMessageBox.information(self, "저장", "이미지 라벨이 저장되었습니다.")

