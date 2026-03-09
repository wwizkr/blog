from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _load_project_env() -> None:
    current = Path(__file__).resolve()
    project_root = None
    for candidate in (current.parent, *current.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "src").exists():
            project_root = candidate
            break
    if project_root is None:
        project_root = current.parents[2]
    load_dotenv(project_root / ".env", override=False)
    load_dotenv(project_root / ".env.local", override=False)


_load_project_env()


@dataclass(frozen=True)
class AppSettings:
    app_name: str = "MubloOps"
    data_dir_name: str = "mublo_ops_data"
    db_file_name: str = "mublo_ops.db"

    @property
    def project_root(self) -> Path:
        current = Path(__file__).resolve()
        for candidate in (current.parent, *current.parents):
            if (candidate / "pyproject.toml").exists() and (candidate / "src").exists():
                return candidate
        return current.parents[2]

    @property
    def preferred_data_dir(self) -> Path:
        return self.project_root / self.data_dir_name

    @property
    def preferred_db_path(self) -> Path:
        return self.preferred_data_dir / self.db_file_name

    @property
    def data_dir(self) -> Path:
        return self.preferred_data_dir

    @property
    def db_path(self) -> Path:
        return self.preferred_db_path

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"


settings = AppSettings()


