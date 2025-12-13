# Digital-Student-Assistant

Цифровой Ассистент Студента - это рекомендательная система студенческих проектов на основе интересов студентов. Большую популярность получили рекомендательные системы на основе больших языковых моделей (LLM). В этом проекте предполагается использование как локальной большой языковой модели (Qwen-14b), так и облачной YandexGPT-5.

![CI](https://github.com/krevetka-is-afk/Digital-Student-Assistant/actions/workflows/ci.yml/badge.svg)

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt
pre-commit install
```

## Ритуал перед PR

```bash
ruff check --fix .
black .
isort .
pytest -q
pre-commit run --all-files
```

## Тесты

```bash
pytest -q
```
