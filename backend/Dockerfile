FROM python:3.11-slim

# Устанавливаем переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Устанавливаем зависимости для работы с Python и сборки зависимостей
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && apt-get clean

# Устанавливаем Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Создаем рабочую директорию
WORKDIR /app

# Копируем файлы для установки зависимостей
COPY pyproject.toml poetry.lock* /app/

# Устанавливаем зависимости
RUN poetry install --no-root

# Копируем все файлы проекта
COPY . /app/

# Применяем миграции
RUN poetry run python manage.py migrate

# Открываем порт
EXPOSE 8000
EXPOSE 8080
