from __future__ import annotations

import atexit
import time
from threading import Lock


class BrowserHtmlFetcher:
    def __init__(self) -> None:
        self._lock = Lock()
        self._driver = None
        self._mode = ""
        self._headless = False
        self._last_error = ""

    def fetch_html(self, url: str, *, headless: bool = False, timeout: int = 15) -> str | None:
        try:
            driver = self._get_driver(headless=headless)
        except Exception as exc:
            self._last_error = str(exc)
            return None

        with self._lock:
            try:
                driver.set_page_load_timeout(max(5, int(timeout)))
                driver.get(url)
                time.sleep(1.2)
                return str(driver.page_source or "")
            except Exception as exc:
                self._last_error = str(exc)
                return None

    def shutdown(self) -> None:
        with self._lock:
            if self._driver is None:
                return
            try:
                self._driver.quit()
            except Exception:
                pass
            finally:
                self._driver = None

    def _get_driver(self, *, headless: bool):
        if self._driver is not None and self._mode == "chrome" and self._headless == bool(headless):
            return self._driver

        self.shutdown()

        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options as ChromeOptions

        options = ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--lang=ko-KR")
        options.add_argument("--window-size=1600,1100")
        if headless:
            options.add_argument("--headless=new")

        driver = webdriver.Chrome(options=options)
        self._driver = driver
        self._mode = "chrome"
        self._headless = bool(headless)
        return driver


browser_html_fetcher = BrowserHtmlFetcher()
atexit.register(browser_html_fetcher.shutdown)
