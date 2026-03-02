from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from labeling import labeling_service
from storage.repositories import LabelRepository


class LabelingPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh_stats()

    def _build_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("라벨링 실행")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        root.addWidget(title)

        stat_box = QGroupBox("통계")
        stat_layout = QHBoxLayout()
        self.stats_label = QLabel("-")
        stat_layout.addWidget(self.stats_label)
        stat_box.setLayout(stat_layout)
        root.addWidget(stat_box)

        run_box = QGroupBox("실행")
        run_layout = QHBoxLayout()
        btn_content = QPushButton("미라벨링 텍스트 라벨링")
        btn_content.clicked.connect(self.run_content_labeling)
        btn_image = QPushButton("미라벨링 이미지 라벨링")
        btn_image.clicked.connect(self.run_image_labeling)
        run_layout.addWidget(btn_content)
        run_layout.addWidget(btn_image)
        run_layout.addStretch(1)
        run_box.setLayout(run_layout)
        root.addWidget(run_box)

        log_box = QGroupBox("실행 로그")
        log_layout = QVBoxLayout()
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        log_layout.addWidget(self.log_view)
        log_box.setLayout(log_layout)
        root.addWidget(log_box, 1)

        self.setLayout(root)

    def refresh_stats(self) -> None:
        stats = LabelRepository.get_label_stats()
        self.stats_label.setText(
            f"콘텐츠: {stats['contents_labeled']}/{stats['contents_total']}  |  "
            f"이미지: {stats['images_labeled']}/{stats['images_total']}"
        )

    def run_content_labeling(self) -> None:
        result = labeling_service.label_unlabeled_contents(limit=300)
        self.log_view.append(f"텍스트 라벨링 완료: {result['labeled']}/{result['target']}")
        self.refresh_stats()

    def run_image_labeling(self) -> None:
        result = labeling_service.label_unlabeled_images(limit=500)
        self.log_view.append(f"이미지 라벨링 완료: {result['labeled']}/{result['target']}")
        self.refresh_stats()


