# -*- coding: utf-8 -*-
import json
import math
import requests
from flask import Flask, render_template, request

# ВАЖНО: папка templates лежит уровнем выше /api
app = Flask(__name__, template_folder="../templates")

# =========================
# Финансовые константы
# =========================

# Чистая почасовая ставка проектировщика (руб/час)
HOURLY_SALARY_NET = 800.0

# Коэффициенты компании
K_TAXES = 1.33       # налоги и взносы
K_OVERHEAD = 1.30    # накладные расходы
K_MARGIN = 0.30      # маржа (30% прибыли)
MIN_PRICE = 35000.0  # минимальная цена всего проекта

# Полная ставка для компании (часовая себестоимость инженера)
RATE_FULL = HOURLY_SALARY_NET * K_TAXES * K_OVERHEAD

# =========================
# Общие коэффициенты проекта
# =========================

OBJECT_TYPE_COEFFS = {
    "Частный дом": 0.95,
    "Коммерция": 1.00,
    "Соц. объект": 1.10,
    "Производство": 1.15,
}

STAGE_COEFFS = {
    "П": 0.60,
    "РД": 1.00,
    "П+РД": 1.20,
}

URGENCY_COEFFS = {
    "Стандартные сроки": 1.00,
    "Срочно": 1.25,
    "Критично": 1.50,
}

SECTION_COMPLEXITY_COEFFS = {
    "Базовая": 1.00,
    "Повышенная": 1.20,
    "Высокая": 1.40,
}

AUTOMATION_LEVEL_COEFFS = {
    "Нет / минимальная автоматика": 1.00,
    "Базовая автоматика / АВР": 1.20,
    "Сложная автоматика, диспетчеризация, АСУ ТП": 1.40,
}

DETAIL_LEVEL_COEFFS = {
    "Основные чертежи и схемы": 1.00,
    "Полный пакет с детализацией (узлы, спецификации)": 1.25,
}

# =========================
# Описание разделов
# =========================

SECTIONS = [
    {
        "key": "pz",
        "title": "Пояснительная записка",
        "group": "Общая часть",
        "base_hours_per_m2": 0.005,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": False,
    },
    {
        "key": "gpzu",
        "title": "Схема планировочной организации земельного участка",
        "group": "Общая часть",
        "base_hours_per_m2": 0.010,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": False,
    },
    {
        "key": "ep",
        "title": "Экскизный проект",
        "group": "Архитектура и конструкция",
        "base_hours_per_m2": 0.030,
        "uses_complexity": True,
        "uses_detail": True,
        "uses_automation": False,
    },
    {
        "key": "ar",
        "title": "Архитектурные решения",
        "group": "Архитектура и конструкция",
        "base_hours_per_m2": 0.050,
        "uses_complexity": True,
        "uses_detail": True,
        "uses_automation": False,
    },
    {
        "key": "kr",
        "title": "Конструктивные решения",
        "group": "Архитектура и конструкция",
        "base_hours_per_m2": 0.055,
        "uses_complexity": True,
        "uses_detail": True,
        "uses_automation": False,
    },
    {
        "key": "electro_internal",
        "title": "Внутренние сети электроснабжения и электроосвещения, молниезащита",
        "group": "Инженерные системы (внутренние)",
        "base_hours_per_m2": 0.060,
        "uses_complexity": True,
        "uses_detail": True,
        "uses_automation": True,
    },
    {
        "key": "ws_internal",
        "title": "Внутренние сети водоснабжения и водоотведения",
        "group": "Инженерные системы (внутренние)",
        "base_hours_per_m2": 0.040,
        "uses_complexity": True,
        "uses_detail": True,
        "uses_automation": False,
    },
    {
        "key": "nvk",
        "title": "НВК",
        "group": "Инженерные системы (внутренние)",
        "base_hours_per_m2": 0.035,
        "uses_complexity": True,
        "uses_detail": True,
        "uses_automation": False,
    },
    {
        "key": "hvac",
        "title": "Отопление, вентиляция и кондиционирование",
        "group": "Инженерные системы (внутренние)",
        "base_hours_per_m2": 0.055,
        "uses_complexity": True,
        "uses_detail": True,
        "uses_automation": False,
    },
    {
        "key": "aitp",
        "title": "АИТП",
        "group": "Инженерные системы (тепло)",
        "base_hours_per_m2": 0.030,
        "uses_complexity": True,
        "uses_detail": True,
        "uses_automation": True,
    },
    {
        "key": "heat_networks",
        "title": "Тепловые сети",
        "group": "Инженерные системы (тепло)",
        "base_hours_per_m2": 0.030,
        "uses_complexity": True,
        "uses_detail": True,
        "uses_automation": False,
    },
    {
        "key": "heat_mech",
        "title": "Тепломеханические решения тепловых сетей",
        "group": "Инженерные системы (тепло)",
        "base_hours_per_m2": 0.025,
        "uses_complexity": True,
        "uses_detail": True,
        "uses_automation": False,
    },
    {
        "key": "fiber",
        "title": "Волокно-оптические линии связи",
        "group": "Связь и слаботочные системы",
        "base_hours_per_m2": 0.020,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": True,
    },
    {
        "key": "tf",
        "title": "ТФ",
        "group": "Связь и слаботочные системы",
        "base_hours_per_m2": 0.015,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": True,
    },
    {
        "key": "sks",
        "title": "СКС",
        "group": "Связь и слаботочные системы",
        "base_hours_per_m2": 0.020,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": True,
    },
    {
        "key": "lvs",
        "title": "ЛВС",
        "group": "Связь и слаботочные системы",
        "base_hours_per_m2": 0.020,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": True,
    },
    {
        "key": "lso",
        "title": "ЛСО",
        "group": "Связь и слаботочные системы",
        "base_hours_per_m2": 0.015,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": False,
    },
    {
        "key": "internet",
        "title": "Интернет",
        "group": "Связь и слаботочные системы",
        "base_hours_per_m2": 0.010,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": True,
    },
    {
        "key": "cctv",
        "title": "Система охранного видеонаблюдения",
        "group": "Безопасность",
        "base_hours_per_m2": 0.020,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": True,
    },
    {
        "key": "skud",
        "title": "СКУД",
        "group": "Безопасность",
        "base_hours_per_m2": 0.020,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": True,
    },
    {
        "key": "fire_extinguish",
        "title": "Пожаротушение",
        "group": "Пожарная безопасность",
        "base_hours_per_m2": 0.030,
        "uses_complexity": True,
        "uses_detail": True,
        "uses_automation": False,
    },
    {
        "key": "aps",
        "title": "Автоматическая пожарная сигнализация",
        "group": "Пожарная безопасность",
        "base_hours_per_m2": 0.025,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": True,
    },
    {
        "key": "soue",
        "title": "СОУЭ",
        "group": "Пожарная безопасность",
        "base_hours_per_m2": 0.015,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": True,
    },
    {
        "key": "automation_dispatch",
        "title": "Система автоматизации и диспетчеризации инженерных систем",
        "group": "Автоматизация",
        "base_hours_per_m2": 0.030,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": True,
    },
    {
        "key": "gochs",
        "title": "Мероприятия гражданской обороны и предупреждения ЧС (ИТМ ГОЧС)",
        "group": "Специальные разделы",
        "base_hours_per_m2": 0.010,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": False,
    },
    {
        "key": "external_comm",
        "title": "Наружные сети связи",
        "group": "Наружные сети",
        "base_hours_per_m2": 0.020,
        "uses_complexity": True,
        "uses_detail": True,
        "uses_automation": False,
    },
    {
        "key": "tech",
        "title": "Технологические решения",
        "group": "Технология",
        "base_hours_per_m2": 0.030,
        "uses_complexity": True,
        "uses_detail": True,
        "uses_automation": False,
    },
    {
        "key": "keo",
        "title": "КЕО",
        "group": "Специальные разделы",
        "base_hours_per_m2": 0.008,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": False,
    },
    {
        "key": "asa",
        "title": "АСА",
        "group": "Специальные разделы",
        "base_hours_per_m2": 0.008,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": False,
    },
    {
        "key": "tbe",
        "title": "ТБЭ",
        "group": "Специальные разделы",
        "base_hours_per_m2": 0.008,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": False,
    },
    {
        "key": "mgn",
        "title": "Мероприятия по обеспечению доступности МГН",
        "group": "Специальные разделы",
        "base_hours_per_m2": 0.008,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": False,
    },
    {
        "key": "pos",
        "title": "Проект организации строительства",
        "group": "Организация строительства",
        "base_hours_per_m2": 0.015,
        "uses_complexity": True,
        "uses_detail": True,
        "uses_automation": False,
    },
    {
        "key": "eco",
        "title": "Мероприятия по охране окружающей среды",
        "group": "Специальные разделы",
        "base_hours_per_m2": 0.010,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": False,
    },
    {
        "key": "fire_measures",
        "title": "Перечень мероприятий по обеспечению пожарной безопасности",
        "group": "Пожарная безопасность",
        "base_hours_per_m2": 0.010,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": False,
    },
    {
        "key": "smeta",
        "title": "Сметная документация",
        "group": "Сметы",
        "base_hours_per_m2": 0.020,
        "uses_complexity": True,
        "uses_detail": False,
        "uses_automation": False,
    },
]

# =========================
# Настройки ИИ (Gemini)
# =========================

# !!! ВСТАВЬ СВОЙ РЕАЛЬНЫЙ КЛЮЧ СЮДА !!!
GEMINI_API_KEY = "AIzaSyA9q6c-CMizuzEbNBC-5cO35VAXEJ4N6AE"

# Идентификатор модели. Если в консоли Google он называется иначе — поменяй.
GEMINI_MODEL = "gemini-2.5-flash"


# =========================
# Вспомогательные функции
# =========================

def format_rub(value):
    """Форматирование числа с разделителями тысяч и 'руб.'."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value
    formatted = f"{value:,.0f}".replace(",", " ")
    return f"{formatted} руб."


app.jinja_env.filters["rub"] = format_rub


def build_gemini_prompt(project_description: str) -> str:
    """Формируем промпт для ИИ, с жёстко заданными вариантами значений."""
    object_types_str = ", ".join(f'"{x}"' for x in OBJECT_TYPE_COEFFS.keys())
    stages_str = ", ".join(f'"{x}"' for x in STAGE_COEFFS.keys())
    urgencies_str = ", ".join(f'"{x}"' for x in URGENCY_COEFFS.keys())
    complexities_str = ", ".join(f'"{x}"' for x in SECTION_COMPLEXITY_COEFFS.keys())
    details_str = ", ".join(f'"{x}"' for x in DETAIL_LEVEL_COEFFS.keys())
    automation_str = ", ".join(f'"{x}"' for x in AUTOMATION_LEVEL_COEFFS.keys())

    sections_lines = []
    for s in SECTIONS:
        sections_lines.append(
            f'- key "{s["key"]}", title "{s["title"]}", '
            f'uses_detail: {str(s["uses_detail"]).lower()}, '
            f'uses_automation: {str(s["uses_automation"]).lower()}'
        )
    sections_block = "\n".join(sections_lines)

    prompt = f"""
Ты — опытный инженер-проектировщик. Тебе дают текстовое описание объекта (на русском).
Нужно предложить, какие разделы проектной документации стоит включить в расчёт стоимости
и какие варианты параметров для них выбрать.

Ограничения: все значения НУЖНО выбирать только из следующих списков, без изменений:

object_type: {object_types_str}
stage: {stages_str}
urgency: {urgencies_str}

complexity: {complexities_str}
detail: {details_str}
automation: {automation_str}

Список разделов (поле key используется в JSON):
{sections_block}

Верни ТОЛЬКО JSON без пояснений по схеме:

{{
  "object_type": "<одно значение из object_type>",
  "stage": "<одно значение из stage>",
  "urgency": "<одно значение из urgency>",
  "sections": {{
    "<section_key>": {{
      "enabled": true или false,
      "complexity": "<одно значение из complexity>",
      "detail": "<одно значение из detail или null>",
      "automation": "<одно значение из automation или null>"
    }},
    ...
  }}
}}

Правила:
- Для разделов, где uses_detail = false, ставь "detail": null.
- Для разделов, где uses_automation = false, ставь "automation": null.
- Если раздел в этом проекте совсем не нужен, можешь либо не включать его в список sections,
  либо указать enabled: false.
- Не добавляй никаких полей, которых нет в схеме.
- Не пиши комментарии, текст до или после JSON.

Описание объекта:
\"\"\"{project_description}\"\"\"
"""
    return prompt.strip()


def call_gemini_for_suggestions(project_description: str):
    """Запрашиваем у Gemini рекомендации по заполнению формы."""
    if not GEMINI_API_KEY or "ВСТАВЬ_СЮДА" in GEMINI_API_KEY:
        raise RuntimeError("API-ключ Gemini не задан в коде (константа GEMINI_API_KEY).")

    prompt = build_gemini_prompt(project_description)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    resp = requests.post(
        url,
        headers=headers,
        params={"key": GEMINI_API_KEY},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    # вытаскиваем текст из первого кандидата
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise RuntimeError("Не удалось прочитать ответ модели Gemini.")

    try:
        raw_json = json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError("Модель вернула некорректный JSON.")

    # нормализуем/проверяем значения
    suggestions = {
        "object_type": None,
        "stage": None,
        "urgency": None,
        "sections": {},
    }

    ot = raw_json.get("object_type")
    if ot in OBJECT_TYPE_COEFFS:
        suggestions["object_type"] = ot

    st = raw_json.get("stage")
    if st in STAGE_COEFFS:
        suggestions["stage"] = st

    urg = raw_json.get("urgency")
    if urg in URGENCY_COEFFS:
        suggestions["urgency"] = urg

    sections_data = raw_json.get("sections", {}) or {}

    for s in SECTIONS:
        skey = s["key"]
        sdata = sections_data.get(skey)
        if not sdata:
            continue

        enabled = bool(sdata.get("enabled", True))

        complexity = sdata.get("complexity")
        if complexity not in SECTION_COMPLEXITY_COEFFS:
            complexity = "Базовая"

        detail = sdata.get("detail")
        if not s.get("uses_detail"):
            detail = None
        else:
            if detail not in DETAIL_LEVEL_COEFFS:
                detail = None

        automation = sdata.get("automation")
        if not s.get("uses_automation"):
            automation = None
        else:
            if automation not in AUTOMATION_LEVEL_COEFFS:
                automation = None

        suggestions["sections"][skey] = {
            "enabled": enabled,
            "complexity": complexity,
            "detail": detail,
            "automation": automation,
            "title": s["title"],
            "group": s["group"],
        }

    return suggestions


def calculate_section_cost(
    section,
    area_m2,
    object_type,
    stage,
    urgency,
    form,
):
    """Расчёт отдельного раздела. Возвращает dict или None, если раздел не включён."""

    key = section["key"]
    enabled = form.get(f"{key}_enabled") == "on"
    if not enabled:
        return None

    # базовая трудоёмкость от площади и типа объекта
    if object_type not in OBJECT_TYPE_COEFFS:
        raise KeyError("Неизвестный тип объекта.")
    object_k = OBJECT_TYPE_COEFFS[object_type]
    t_base = area_m2 * section["base_hours_per_m2"] * object_k

    # сложность
    complexity_choice = form.get(f"{key}_complexity") or "Базовая"
    if complexity_choice not in SECTION_COMPLEXITY_COEFFS:
        raise KeyError(f"Неизвестная сложность для раздела {section['title']}.")
    k_complexity = SECTION_COMPLEXITY_COEFFS[complexity_choice]

    # детализация
    k_detail = 1.0
    detail_choice = None
    if section.get("uses_detail"):
        detail_choice = form.get(f"{key}_detail")
        if not detail_choice:
            raise ValueError(f"Не выбрана детализация для раздела: {section['title']}.")
        if detail_choice not in DETAIL_LEVEL_COEFFS:
            raise KeyError(f"Неизвестный уровень детализации для раздела {section['title']}.")
        k_detail = DETAIL_LEVEL_COEFFS[detail_choice]

    # автоматика
    k_automation = 1.0
    automation_choice = None
    if section.get("uses_automation"):
        automation_choice = form.get(f"{key}_automation")
        if not automation_choice:
            raise ValueError(f"Не выбран уровень автоматики для раздела: {section['title']}.")
        if automation_choice not in AUTOMATION_LEVEL_COEFFS:
            raise KeyError(f"Неизвестный уровень автоматики для раздела {section['title']}.")
        k_automation = AUTOMATION_LEVEL_COEFFS[automation_choice]

    # стадия и срочность
    if stage not in STAGE_COEFFS:
        raise KeyError("Неизвестная стадия проекта.")
    if urgency not in URGENCY_COEFFS:
        raise KeyError("Неизвестный уровень срочности.")

    k_stage = STAGE_COEFFS[stage]
    k_urgency = URGENCY_COEFFS[urgency]

    # общий коэффициент
    k_total = (
        k_complexity
        * k_detail
        * k_automation
        * k_stage
        * k_urgency
    )

    t_adjusted_raw = t_base * k_total
    t_adjusted = math.ceil(t_adjusted_raw)

    cost_company = t_adjusted * RATE_FULL
    cost_client = cost_company * (1.0 + K_MARGIN)

    return {
        "key": key,
        "title": section["title"],
        "group": section["group"],
        "enabled": True,
        "t_base": t_base,
        "t_adjusted": t_adjusted,
        "k_total": k_total,
        "cost_company": cost_company,
        "cost_client": cost_client,
        "complexity_choice": complexity_choice,
        "detail_choice": detail_choice,
        "automation_choice": automation_choice,
        "coeffs": {
            "k_complexity": k_complexity,
            "k_detail": k_detail,
            "k_automation": k_automation,
            "k_stage": k_stage,
            "k_urgency": k_urgency,
            "k_object_type": object_k,
        },
    }


# =========================
# Flask-маршрут
# =========================

@app.route("/", methods=["GET", "POST"])
def multi_section_calculator():
    error_message = None           # ошибки расчёта стоимости
    ai_error_message = None        # ошибки интеграции с ИИ
    ai_suggestions = None          # рекомендации ИИ
    section_results = []           # результаты расчёта по разделам
    totals = None                  # итоговые суммы

    form_data = {
        "project_description": "",
        "area": "",
        "object_type": None,
        "stage": None,
        "urgency": None,
    }

    if request.method == "POST":
        action = request.form.get("action") or "calculate"

        # сохраняем введённые значения
        form_data["project_description"] = request.form.get("project_description", "").strip()
        form_data["area"] = request.form.get("area", "").strip()
        form_data["object_type"] = request.form.get("object_type")
        form_data["stage"] = request.form.get("stage")
        form_data["urgency"] = request.form.get("urgency")

        # --- Режим: запрос рекомендаций ИИ ---
        if action == "suggest":
            if not form_data["project_description"]:
                ai_error_message = "Опишите объект, чтобы получить рекомендации от ИИ."
            else:
                try:
                    ai_suggestions = call_gemini_for_suggestions(form_data["project_description"])
                except Exception as exc:
                    ai_error_message = f"Не удалось получить рекомендации ИИ: {exc}"

        # --- Режим: расчёт стоимости ---
        elif action == "calculate":
            try:
                area_str = (request.form.get("area") or "").replace(",", ".").strip()
                if not area_str:
                    raise ValueError("Не указана площадь объекта.")
                area_m2 = float(area_str)
                if area_m2 <= 0:
                    raise ValueError("Площадь должна быть больше нуля.")

                object_type = request.form.get("object_type")
                stage = request.form.get("stage")
                urgency = request.form.get("urgency")

                if not object_type:
                    raise ValueError("Не выбран тип объекта.")
                if not stage:
                    raise ValueError("Не выбрана стадия проекта (П / РД / П+РД).")
                if not urgency:
                    raise ValueError("Не выбрана срочность выполнения.")

                # расчёт по разделам
                for section in SECTIONS:
                    result = calculate_section_cost(
                        section=section,
                        area_m2=area_m2,
                        object_type=object_type,
                        stage=stage,
                        urgency=urgency,
                        form=request.form,
                    )
                    if result is not None:
                        section_results.append(result)

                if not section_results:
                    raise ValueError("Не выбран ни один раздел для расчёта.")

                total_hours = sum(r["t_adjusted"] for r in section_results)
                total_company = sum(r["cost_company"] for r in section_results)
                total_client_before_min = sum(r["cost_client"] for r in section_results)
                total_client_final = max(total_client_before_min, MIN_PRICE)

                totals = {
                    "total_hours": total_hours,
                    "total_company": total_company,
                    "total_client_before_min": total_client_before_min,
                    "total_client_final": total_client_final,
                    "applied_min_price": (
                        total_client_before_min < MIN_PRICE
                        and total_client_final == MIN_PRICE
                    ),
                }

            except Exception as exc:
                error_message = str(exc)

    # группировка разделов по group для шаблона
    grouped_sections = {}
    for s in SECTIONS:
        grouped_sections.setdefault(s["group"], []).append(s)

    return render_template(
        "calculator.html",
        object_types=list(OBJECT_TYPE_COEFFS.keys()),
        stages=list(STAGE_COEFFS.keys()),
        urgencies=list(URGENCY_COEFFS.keys()),
        section_complexities=list(SECTION_COMPLEXITY_COEFFS.keys()),
        automation_levels=list(AUTOMATION_LEVEL_COEFFS.keys()),
        detail_levels=list(DETAIL_LEVEL_COEFFS.keys()),
        sections=SECTIONS,
        grouped_sections=grouped_sections,
        rate_full=RATE_FULL,
        margin=K_MARGIN,
        min_price=MIN_PRICE,
        section_results=section_results,
        totals=totals,
        error_message=error_message,
        ai_error_message=ai_error_message,
        ai_suggestions=ai_suggestions,
        form_data=form_data,
    )


if __name__ == "__main__":
    app.run(debug=True)

