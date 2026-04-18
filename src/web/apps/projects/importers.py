import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import ZipFile

from django.db import transaction

from .models import EPP, Project, ProjectSourceType
from .transitions import apply_imported_status

XML_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
EXPECTED_HEADERS = [
    "Номер ЭПП",
    "Наименование ЭПП",
    "Номер кампании",
    "Наименование кампании",
    "Дата создания вакансии/темы",
    "Дата старта подачи заявок",
    "Дата окончания подачи заявок",
    "Дата начала работ",
    "Дата окончания работ",
    "Статус вакансии/темы",
    "Дата смены статуса вакансии/темы",
    "Наименование вакансии",
    "Наименование вакансии на английском языке",
    "Тема ВКР/КР",
    "Тема ВКР/КР на английском языкке",
    "Язык реализации",
    "Тип активности",
    "Руководитель вакансии/темы",
    "E-mail руководителя",
    "Структурное подразделение руководителя",
    "Категория персонала руководителя",
    "Внутренние соруководители вакансии/темы",
    'ВКР "Стартап как диплом"',
    "Количество мест для подачи заявок",
    "Количество актуальных заявок",
    "Кредиты",
    "Количество часов нагрузки/занятости на студента (в неделю)",
    "Форма контроля",
    "Формат работы",
    "Формат участия студентов",
    "Формат представления и защиты результатов",
    "Формула оценки результатов",
    "Особенности реализации",
    "Критерии отбора",
    "Предполагается оплата за участие",
    "Возможность пересдач",
    "Место реализации",
    "Внутренний заказчик",
    "Место нахождения внешней организации",
    "Внешний заказчик",
    "ИНН",
    "Полное ФИО адвоката/нотариуса/представителя СМИ",
    "Полное наименование Адвокатской палаты/Нотариальной палаты/СМИ",
    "Регистрационный номер минюста (только для нотариуса/адвоката)",
    "Номер лицензии (нотариус/адвокат/СМИ)",
    "Тип организации",
    "Тип сотрудничества",
    "Статус заключения договора о практической подготовке",
    "Номер договора",
    "Дата договора",
    "Планируется ли использование ИИ в работе",
    "Использование Цифровых инструментов",
    "Области использования",
    "Библиотеки Python",
    "Методы",
    "Языки программирования",
    "Программы и языки программирования для обработки данных и моделирования",
    "Инструменты и методы для работы с данными",
    "Инициатор вакансии/темы",
    "Тип инициатора",
    "Теги вакансии",
]
REQUIRED_ROW_HEADERS = {
    "Номер ЭПП",
    "Наименование вакансии",
    "Статус вакансии/темы",
}


def default_epp_xlsx_path() -> Path:
    return Path(__file__).resolve().parents[4] / "docs" / "data_source" / "EPP.xlsx"


@dataclass
class ImportStats:
    epp_created: int = 0
    epp_updated: int = 0
    projects_created: int = 0
    projects_updated: int = 0
    skipped: int = 0
    errors: int = 0
    warnings: int = 0


class XlsxReader:
    def __init__(self, path: Path):
        self.path = path

    def rows(self) -> list[list[str]]:
        with ZipFile(self.path) as archive:
            shared_strings = self._shared_strings(archive)
            root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            data = root.find("main:sheetData", XML_NS)
            if data is None:
                return []
            return [
                self._parse_row(row, shared_strings) for row in data.findall("main:row", XML_NS)
            ]

    def _shared_strings(self, archive: ZipFile) -> list[str]:
        if "xl/sharedStrings.xml" not in archive.namelist():
            return []
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        strings: list[str] = []
        for item in root.findall("main:si", XML_NS):
            strings.append("".join(node.text or "" for node in item.iterfind(".//main:t", XML_NS)))
        return strings

    def _parse_row(self, row, shared_strings: list[str]) -> list[str]:
        values: list[str] = []
        for cell in row.findall("main:c", XML_NS):
            cell_ref = cell.attrib.get("r", "")
            target_index = column_index_from_reference(cell_ref)
            while len(values) < target_index:
                values.append("")
            values.append(self._parse_cell(cell, shared_strings))
        return values

    def _parse_cell(self, cell, shared_strings: list[str]) -> str:
        cell_type = cell.attrib.get("t")
        if cell_type == "inlineStr":
            inline = cell.find("main:is", XML_NS)
            if inline is None:
                return ""
            return "".join(node.text or "" for node in inline.iterfind(".//main:t", XML_NS))
        value = cell.find("main:v", XML_NS)
        if value is None or value.text is None:
            return ""
        raw = value.text
        if cell_type == "s":
            return (
                shared_strings[int(raw)]
                if raw.isdigit() and int(raw) < len(shared_strings)
                else raw
            )
        return raw


def parse_bool(value: str) -> bool | None:
    normalized = value.strip().lower()
    if not normalized:
        return None
    truthy = {"да", "true", "1", "yes", "+"}
    falsy = {"нет", "false", "0", "no", "-"}
    if normalized in truthy:
        return True
    if normalized in falsy:
        return False
    return None


def column_index_from_reference(cell_reference: str) -> int:
    letters = "".join(char for char in cell_reference if char.isalpha())
    if not letters:
        return 0
    result = 0
    for char in letters:
        result = result * 26 + (ord(char.upper()) - ord("A") + 1)
    return result - 1


def parse_int(value: str) -> int | None:
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return int(Decimal(normalized.replace(",", ".")))
    except (InvalidOperation, ValueError):
        return None


def parse_decimal(value: str) -> Decimal | None:
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return Decimal(normalized.replace(",", "."))
    except InvalidOperation:
        return None


def parse_date(value: str) -> date | None:
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def parse_datetime(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None
    normalized = normalized.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def build_source_ref(payload: dict[str, str], row_index: int) -> str:
    stable_key = "|".join(
        [
            payload.get("Номер ЭПП", "").strip(),
            payload.get("Наименование вакансии", "").strip(),
            payload.get("Руководитель вакансии/темы", "").strip(),
            payload.get("Дата создания вакансии/темы", "").strip(),
            str(row_index),
        ]
    )
    return hashlib.sha256(stable_key.encode("utf-8")).hexdigest()


def build_description(payload: dict[str, str]) -> str:
    parts = [
        payload.get("Особенности реализации", "").strip(),
        payload.get("Критерии отбора", "").strip(),
        payload.get("Формат работы", "").strip(),
        payload.get("Формат участия студентов", "").strip(),
    ]
    return "\n\n".join(part for part in parts if part)


def build_tech_tags(payload: dict[str, str]) -> list[str]:
    items: list[str] = []
    for raw_value in (
        payload.get("Библиотеки Python", ""),
        payload.get("Методы", ""),
        payload.get("Языки программирования", "")
        or payload.get(
            "Программы и языки программирования для обработки данных и моделирования", ""
        ),
        payload.get("Инструменты и методы для работы с данными", ""),
        payload.get("Теги вакансии", ""),
    ):
        if not raw_value:
            continue
        pieces = [item.strip() for item in str(raw_value).replace(";", ",").split(",")]
        items.extend(piece for piece in pieces if piece)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        marker = item.lower()
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(item)
    return deduped


def validate_headers(headers: list[str]) -> None:
    if headers != EXPECTED_HEADERS:
        raise ValueError("Unexpected EPP.xlsx header contract.")


def row_to_payload(headers: list[str], values: list[str]) -> dict[str, str]:
    normalized = list(values) + [""] * max(0, len(headers) - len(values))
    return {header: normalized[index] for index, header in enumerate(headers)}


def map_epp_fields(payload: dict[str, str]) -> dict[str, object]:
    return {
        "title": payload.get("Наименование ЭПП", "").strip(),
        "campaign_ref": payload.get("Номер кампании", "").strip(),
        "campaign_title": payload.get("Наименование кампании", "").strip(),
        "created_at_source": parse_datetime(payload.get("Дата создания вакансии/темы", "")),
        "start_date": parse_date(payload.get("Дата начала работ", "")),
        "end_date": parse_date(payload.get("Дата окончания работ", "")),
        "supervisor_name": payload.get("Руководитель вакансии/темы", "").strip(),
        "supervisor_email": payload.get("E-mail руководителя", "").strip(),
        "supervisor_department": payload.get("Структурное подразделение руководителя", "").strip(),
        "initiator_name": payload.get("Инициатор вакансии/темы", "").strip(),
        "initiator_type": payload.get("Тип инициатора", "").strip(),
        "status_raw": payload.get("Статус вакансии/темы", "").strip(),
        "raw_payload": {
            header: payload.get(header, "")
            for header in [
                "Номер ЭПП",
                "Наименование ЭПП",
                "Номер кампании",
                "Наименование кампании",
                "Дата создания вакансии/темы",
                "Дата начала работ",
                "Дата окончания работ",
                "Руководитель вакансии/темы",
                "E-mail руководителя",
                "Структурное подразделение руководителя",
                "Инициатор вакансии/темы",
                "Тип инициатора",
                "Статус вакансии/темы",
            ]
        },
    }


def map_project_fields(payload: dict[str, str], row_index: int, epp: EPP) -> dict[str, object]:
    project_fields: dict[str, object] = {
        "epp": epp,
        "source_type": ProjectSourceType.EPP,
        "source_ref": build_source_ref(payload, row_index),
        "source_row_index": row_index,
        "title": payload.get("Наименование вакансии", "").strip(),
        "description": build_description(payload),
        "tech_tags": build_tech_tags(payload),
        "vacancy_title": payload.get("Наименование вакансии", "").strip(),
        "vacancy_title_en": payload.get("Наименование вакансии на английском языке", "").strip(),
        "thesis_title": payload.get("Тема ВКР/КР", "").strip(),
        "thesis_title_en": payload.get("Тема ВКР/КР на английском языкке", "").strip(),
        "implementation_language": payload.get("Язык реализации", "").strip(),
        "activity_type": payload.get("Тип активности", "").strip(),
        "supervisor_name": payload.get("Руководитель вакансии/темы", "").strip(),
        "supervisor_email": payload.get("E-mail руководителя", "").strip(),
        "supervisor_department": payload.get("Структурное подразделение руководителя", "").strip(),
        "supervisor_staff_category": payload.get("Категория персонала руководителя", "").strip(),
        "co_supervisors": payload.get("Внутренние соруководители вакансии/темы", "").strip(),
        "startup_as_thesis": parse_bool(payload.get('ВКР "Стартап как диплом"', "")),
        "team_size": parse_int(payload.get("Количество мест для подачи заявок", "")) or 1,
        "application_opened_at": parse_date(payload.get("Дата старта подачи заявок", "")),
        "application_deadline": parse_date(payload.get("Дата окончания подачи заявок", "")),
        "applications_count_source": parse_int(payload.get("Количество актуальных заявок", "")),
        "credits": parse_decimal(payload.get("Кредиты", "")),
        "hours_per_week": parse_decimal(
            payload.get("Количество часов нагрузки/занятости на студента (в неделю)", "")
        ),
        "control_form": payload.get("Форма контроля", "").strip(),
        "work_format": payload.get("Формат работы", "").strip(),
        "student_participation_format": payload.get("Формат участия студентов", "").strip(),
        "results_presentation_format": payload.get(
            "Формат представления и защиты результатов", ""
        ).strip(),
        "grading_formula": payload.get("Формула оценки результатов", "").strip(),
        "implementation_features": payload.get("Особенности реализации", "").strip(),
        "selection_criteria": payload.get("Критерии отбора", "").strip(),
        "is_paid": parse_bool(payload.get("Предполагается оплата за участие", "")),
        "retakes_allowed": parse_bool(payload.get("Возможность пересдач", "")),
        "location": payload.get("Место реализации", "").strip(),
        "internal_customer": payload.get("Внутренний заказчик", "").strip(),
        "external_customer_location": payload.get(
            "Место нахождения внешней организации", ""
        ).strip(),
        "external_customer": payload.get("Внешний заказчик", "").strip(),
        "inn": payload.get("ИНН", "").strip(),
        "organization_type": payload.get("Тип организации", "").strip(),
        "cooperation_type": payload.get("Тип сотрудничества", "").strip(),
        "practice_contract_status": payload.get(
            "Статус заключения договора о практической подготовке", ""
        ).strip(),
        "contract_number": payload.get("Номер договора", "").strip(),
        "contract_date": parse_date(payload.get("Дата договора", "")),
        "uses_ai": parse_bool(payload.get("Планируется ли использование ИИ в работе", "")),
        "digital_tools": payload.get("Использование Цифровых инструментов", "").strip(),
        "usage_areas": payload.get("Области использования", "").strip(),
        "python_libraries": payload.get("Библиотеки Python", "").strip(),
        "methods": payload.get("Методы", "").strip(),
        "programming_languages": payload.get("Языки программирования", "").strip()
        or payload.get(
            "Программы и языки программирования для обработки данных и моделирования", ""
        ).strip(),
        "data_tools": payload.get("Инструменты и методы для работы с данными", "").strip(),
        "vacancy_initiator": payload.get("Инициатор вакансии/темы", "").strip(),
        "vacancy_initiator_type": payload.get("Тип инициатора", "").strip(),
        "vacancy_tags": payload.get("Теги вакансии", "").strip(),
        "status_raw": payload.get("Статус вакансии/темы", "").strip(),
        "raw_payload": dict(payload),
    }
    return project_fields


@transaction.atomic
def upsert_from_payload(payload: dict[str, str], row_index: int) -> tuple[bool, bool, bool]:
    epp_ref = payload.get("Номер ЭПП", "").strip()
    if not epp_ref:
        raise ValueError("Missing EPP source reference.")

    epp_defaults = map_epp_fields(payload)
    epp, epp_created = EPP.objects.update_or_create(source_ref=epp_ref, defaults=epp_defaults)

    source_ref = build_source_ref(payload, row_index)
    project_defaults = map_project_fields(payload, row_index, epp)
    project, project_created = Project.objects.get_or_create(
        source_type=ProjectSourceType.EPP,
        source_ref=source_ref,
        defaults=project_defaults,
    )

    warning = False
    status_raw = str(project_defaults["status_raw"])
    if project_created:
        apply_imported_status(project, status_raw)
        for field, value in project_defaults.items():
            setattr(project, field, value)
        project.save()
    else:
        project_status_before = project.status
        for field, value in project_defaults.items():
            setattr(project, field, value)
        project, warning = apply_imported_status(project, status_raw)
        project.save()
        if project_status_before == project.status and warning:
            warning = True

    return epp_created, project_created, warning


def import_epp_xlsx(path: Path) -> ImportStats:
    rows = XlsxReader(path).rows()
    if not rows:
        raise ValueError("EPP.xlsx is empty.")
    headers = rows[0]
    validate_headers(headers)
    stats = ImportStats()
    for row_index, values in enumerate(rows[1:], start=2):
        payload = row_to_payload(headers, values)
        if not any(str(payload.get(header, "")).strip() for header in headers):
            stats.skipped += 1
            continue
        if not all(payload.get(header, "").strip() for header in REQUIRED_ROW_HEADERS):
            stats.skipped += 1
            continue
        try:
            epp_created, project_created, warning = upsert_from_payload(payload, row_index)
        except Exception:
            stats.errors += 1
            continue
        if epp_created:
            stats.epp_created += 1
        else:
            stats.epp_updated += 1
        if project_created:
            stats.projects_created += 1
        else:
            stats.projects_updated += 1
        if warning:
            stats.warnings += 1
    return stats
