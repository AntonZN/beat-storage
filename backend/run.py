import logging
import multiprocessing
import os
from loguru import logger

from gunicorn.app.base import BaseApplication

LOG_LEVEL = logging.getLevelName(os.environ.get("LOG_LEVEL", "DEBUG"))


class InterceptHandler(logging.Handler):
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, f"{record.getMessage()}"
        )


class CustomGunicornApplication(BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        for key, value in self.options.items():
            if key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


if __name__ == "__main__":
    from src.asgi import api, django_application

    logging.basicConfig(handlers=[InterceptHandler()], level=0)
    logging.getLogger("asyncio").setLevel(logging.ERROR)

    options_api = {
        "bind": "0.0.0.0:8080",
        "workers": 3,
        "accesslog": "-",
        "errorlog": "-",
        "worker_class": "uvicorn.workers.UvicornWorker",
    }

    options_admin = {
        "bind": "0.0.0.0:8000",
        "workers": 3,
        "accesslog": "-",
        "errorlog": "-",
        "worker_class": "uvicorn.workers.UvicornWorker",
    }

    gunicorn_app_api = CustomGunicornApplication(api, options=options_api)
    gunicorn_application = CustomGunicornApplication(
        django_application, options=options_admin
    )
    multiprocessing.Process(target=gunicorn_application.run).start()
    multiprocessing.Process(target=gunicorn_app_api.run).start()
