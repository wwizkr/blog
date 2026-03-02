from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    app_name: str = "BlogWriter"
    data_dir_name: str = "blogwriter_data"
    db_file_name: str = "blogwriter.db"

    @property
    def project_root(self) -> Path:
        current = Path(__file__).resolve()
        for candidate in (current.parent, *current.parents):
            if (candidate / "pyproject.toml").exists() and (candidate / "src").exists():
                return candidate
        return current.parents[2]
    @property
    def data_dir(self) -> Path:
        return self.project_root / self.data_dir_name

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_file_name

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"


settings = AppSettings()


