import random

# llm_analyzer.py
import glob
import pandas as pd
import time
from openai import OpenAI
import numpy as np
import re
import os
global  mean_score
from catboost import CatBoostClassifier

API_KEY = "NGNiZjk4NTAtZTdiZS00YTYwLTg5YTktZDYxOGFkMmZhZGVh.a24ed12f27388b64e98fd9f9d207dd21"

url = "https://foundation-models.api.cloud.ru/v1"

models_to_use = [
    "Qwen/Qwen3-235B-A22B-Instruct-2507",
    "GigaChat/GigaChat-2-Max",
    "Qwen/Qwen3-Next-80B-A3B-Instruct"
]

# Добавляем API_KEY и timeout в client_params
client_params = {
    "api_key": API_KEY, # <-- Используем встроенный ключ
    "base_url": url,
    "timeout": 20 # <-- Таймаут 20 секунд
}

generation_params = {
    "max_tokens": 10,
    "temperature": 0.3,
    "presence_penalty": 0,
    "top_p": 0.95,
}
# --- Конец параметров ---

def extract_number_from_response(response_text):
    """Пытается извлечь первое число от 1 до 5 из текста ответа LLM."""
    if response_text is None:
        print(f"  Предупреждение: Ответ LLM пуст (None). Используем 3.")
        return 3

    match = re.search(r'\b([1-5])\b', str(response_text))
    if match:
        return int(match.group(1))
    print(f"  Предупреждение: Не удалось извлечь число из ответа '{response_text}'. Используем 3.")
    return 3

def query_llm_sync(model_name, prompt, client_params, generation_params):
    """Отправляет запрос одной LLM и возвращает число от 1 до 5."""
    client = OpenAI(**client_params) # <-- Создаём клиента с встроенным ключом и таймаутом
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": f"Оцени риск гипоксии плода по анамнезу пациента. Ответь только числом от 1 до 5, где 1 — минимальный риск, 5 — максимальный риск.\n\nАнамнез: {prompt}"
                }
            ],
            **generation_params
        )
        answer_text = response.choices[0].message.content
        score = extract_number_from_response(answer_text)
        print(f"    Модель {model_name} выдала: {answer_text.strip()} -> {score}")
        return score
    except Exception as e: # Ловим все ошибки, включая таймаут
        print(f"    Ошибка при запросе к {model_name}: {e}")
        return 3

def diagnoz_analyze(file_paths, anamnesis):
    global mean_score
    #удаление временных датафреймов для фич
    reset_accumulated_data()
    """
    Анализирует анамнез с помощью 3 LLM и возвращает среднюю оценку риска гипоксии (число от 1 до 5).
    Если модель не отвечает дольше 20 секунд, возвращается 3.

    Args:
        file_paths: (игнорируется) Список путей к файлам физиологических данных.
        anamnesis: (str) Строка с текстом анамнеза пациента.

    Returns:
        float: Средняя оценка риска гипоксии от 1 до 5.
    """
    print(f"Анализ анамнеза: {anamnesis}") # Опционально
    scores = []
    for model_name in models_to_use:
        score = query_llm_sync(model_name, str(anamnesis), client_params, generation_params)
        scores.append(score)
        time.sleep(0.1) # Задержка между запросами

    mean_score = np.mean(scores)
    print(f"Оценки от моделей {models_to_use}: {scores} -> Средняя оценка: {mean_score:.2f}") # Опционально
    #return mean_score  Возвращаем среднее (mean_score)



# Путь к файлу модели
MODEL_PATH = 'final_catboost_model.cbm'
model = None  # Глобальная переменная для модели, чтобы загрузить её один раз

# Пути к временным файлам для накопления данных
TEMP_DIR = 'temp'
COMBINED_BPM_PATH = os.path.join(TEMP_DIR, 'combined_bpm.csv')
COMBINED_UTERUS_PATH = os.path.join(TEMP_DIR, 'combined_uterus.csv')


# --- Вспомогательные функции ---
def load_full_file(filepath):
    """Загружает весь CSV файл."""
    try:
        df = pd.read_csv(filepath)
        return df
    except pd.errors.EmptyDataError:
        print(f"Предупреждение: файл {filepath} пуст.")
        return pd.DataFrame(columns=['time_sec', 'value'])
    except Exception as e:
        print(f"Ошибка при чтении файла {filepath}: {e}")
        return pd.DataFrame(columns=['time_sec', 'value'])


def save_full_file(df, filepath):
    """Сохраняет DataFrame в CSV файл."""
    try:
        df.to_csv(filepath, index=False)
        # print(f"✅ Файл сохранён: {filepath}")
    except Exception as e:
        print(f"Ошибка при сохранении файла {filepath}: {e}")
        raise


def initialize_temp_files():
    """Создаёт временную директорию и пустые временные файлы, если они не существуют."""
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
        print(f"📁 Создана директория для временных файлов: {TEMP_DIR}")

    # Если временные файлы не существуют, создаём пустые
    if not os.path.exists(COMBINED_BPM_PATH):
        empty_df = pd.DataFrame(columns=['time_sec', 'value'])
        save_full_file(empty_df, COMBINED_BPM_PATH)
    if not os.path.exists(COMBINED_UTERUS_PATH):
        empty_df = pd.DataFrame(columns=['time_sec', 'value'])
        save_full_file(empty_df, COMBINED_UTERUS_PATH)


def calculate_features_for_combined_session(combined_bpm_df, combined_uterus_df):
    """Вычисляет фичи для объединённых данных."""
    mean_bpm = std_bpm = mean_uterus = std_uterus = np.nan

    if not combined_bpm_df.empty:
        # Проверка, что колонка 'value' существует
        if 'value' not in combined_bpm_df.columns:
            raise KeyError(f"Колонка 'value' не найдена в combined_bpm_df. Колонки: {list(combined_bpm_df.columns)}")
        mean_bpm = combined_bpm_df['value'].mean()
        std_bpm = combined_bpm_df['value'].std(ddof=1)  # ddof=1 для несмещенной оценки СКО

    if not combined_uterus_df.empty:
        # Проверка, что колонка 'value' существует
        if 'value' not in combined_uterus_df.columns:
            raise KeyError(
                f"Колонка 'value' не найдена в combined_uterus_df. Колонки: {list(combined_uterus_df.columns)}")
        mean_uterus = combined_uterus_df['value'].mean()
        std_uterus = combined_uterus_df['value'].std(ddof=1)

    print(f"🧮 Вычисленные фичи на объединённых данных:")
    print(f"   mean_bpm: {mean_bpm:.2f}, std_bpm: {std_bpm:.2f}")
    print(f"   mean_uterus: {mean_uterus:.2f}, std_uterus: {std_uterus:.2f}")

    return mean_bpm, std_bpm, mean_uterus, std_uterus


# --- Основная функция ---
def analyze_data(file_paths):
    """
    Анализирует физиологические данные из файлов bpm_n.csv и uterus_n.csv,
    объединяет их с ранее обработанными данными, вычисляет фичи
    на основе всех накопленных данных и возвращает прогноз
    на основе обученной модели CatBoost.

    Args:
        file_paths (list): Список из двух путей: [путь_к_bpm_n.csv, путь_к_uterus_n.csv].

    Returns:
        dict: Словарь с результатами анализа, включая вероятность гипоксии в процентах.
    """
    global mean_score, model

    # - 0. Инициализация временных файлов -
    initialize_temp_files()

    # - 1. Проверка входных данных -
    if not isinstance(file_paths, list) or len(file_paths) != 2:
        raise ValueError("file_paths должен быть списком из двух путей к файлам bpm и uterus.")

    bpm_file_path, uterus_file_path = file_paths
    if not os.path.isfile(bpm_file_path):
        raise FileNotFoundError(f"Файл bpm не найден: {bpm_file_path}")
    if not os.path.isfile(uterus_file_path):
        raise FileNotFoundError(f"Файл uterus не найден: {uterus_file_path}")

    # - 2. Получение mean_score -
    risk_level = mean_score
    if risk_level is None:
        print("⚠️ Предупреждение: mean_score не установлен. Используется значение 3.0.")
        risk_level = 3.0
    print(f"📊 analyze_data использует mean_score (анамнез LLM) = {risk_level}")

    # - 3. Загрузка модели (один раз) -
    if model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Модель не найдена по пути: {MODEL_PATH}. Убедитесь, что модель была обучена и сохранена.")
        try:
            model = CatBoostClassifier() # Создаем пустую модель
            model.load_model(MODEL_PATH) # Загружаем обученные веса
            print(f"✅ Модель CatBoost загружена из {MODEL_PATH}")
        except Exception as e:
            print(f"❌ Ошибка при загрузке модели: {e}")
            raise e

    # - 4. Загрузка текущих файлов -
    try:
        df_current_bpm = load_full_file(bpm_file_path)
        df_current_uterus = load_full_file(uterus_file_path)
        print(f"✅ Загружены текущие файлы: {bpm_file_path}, {uterus_file_path}")
    except Exception as e:
        error_msg = f"Ошибка при загрузке текущих файлов: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)

    # - 5. Вычисление фичей на основе ТЕКУЩЕЙ пары файлов (до объединения) -
    try:
        mean_bpm_current = df_current_bpm['value'].mean()
        std_bpm_current = df_current_bpm['value'].std()
        mean_uterus_current = df_current_uterus['value'].mean()
        std_uterus_current = df_current_uterus['value'].std()
        print(f"🧮 Вычисленные фичи на текущей паре файлов:")
        print(f" mean_bpm_current: {mean_bpm_current:.2f}, std_bpm_current: {std_bpm_current:.2f}")
        print(f" mean_uterus_current: {mean_uterus_current:.2f}, std_uterus_current: {std_uterus_current:.2f}")
    except Exception as e:
        error_msg = f"Ошибка при вычислении фич из текущей пары файлов: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)

    # - 6. Загрузка ранее объединённых данных -
    try:
        df_combined_bpm = load_full_file(COMBINED_BPM_PATH)
        df_combined_uterus = load_full_file(COMBINED_UTERUS_PATH)
        print(f"📂 Загружены ранее объединённые данные из {COMBINED_BPM_PATH} и {COMBINED_UTERUS_PATH}")
    except Exception as e:
        error_msg = f"Ошибка при загрузке ранее объединённых файлов: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)

    # - 7. Объединение текущих данных с ранее объединёнными (аналог combine_with_existing_data) -
    try:
        # Объединяем bpm
        if not df_current_bpm.empty:
            # Вычисляем смещение времени для текущего bpm файла
            time_offset_bpm = 0.0
            if not df_combined_bpm.empty:
                time_offset_bpm = df_combined_bpm['time_sec'].iloc[-1] if 'time_sec' in df_combined_bpm.columns and not df_combined_bpm.empty else 0.0
            df_current_bpm_copy = df_current_bpm.copy()
            df_current_bpm_copy['time_sec'] += time_offset_bpm
            df_new_combined_bpm = pd.concat([df_combined_bpm, df_current_bpm_copy], ignore_index=True)
        else:
            df_new_combined_bpm = df_combined_bpm # Остается старый, если новый пуст

        # Объединяем uterus
        if not df_current_uterus.empty:
            # Вычисляем смещение времени для текущего uterus файла
            time_offset_uterus = 0.0
            if not df_combined_uterus.empty:
                time_offset_uterus = df_combined_uterus['time_sec'].iloc[-1] if 'time_sec' in df_combined_uterus.columns and not df_combined_uterus.empty else 0.0
            df_current_uterus_copy = df_current_uterus.copy()
            df_current_uterus_copy['time_sec'] += time_offset_uterus
            df_new_combined_uterus = pd.concat([df_combined_uterus, df_current_uterus_copy], ignore_index=True)
        else:
            df_new_combined_uterus = df_combined_uterus # Остается старый, если новый пуст

        print(f"🔗 Объединены текущие данные с ранее накопленными.")
    except Exception as e:
        error_msg = f"Ошибка при объединении данных: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)

    # - 8. Сохранение новых объединённых данных -
    try:
        save_full_file(df_new_combined_bpm, COMBINED_BPM_PATH)
        save_full_file(df_new_combined_uterus, COMBINED_UTERUS_PATH)
        print(f"💾 Новые объединённые данные сохранены в {COMBINED_BPM_PATH} и {COMBINED_UTERUS_PATH}")
    except Exception as e:
        error_msg = f"Ошибка при сохранении новых объединённых файлов: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)

    # - 9. Вычисление фич на основе ВСЕХ объединённых данных (для CatBoost и глобальных проверок) -
    try:
        mean_bpm, std_bpm, mean_uterus, std_uterus = calculate_features_for_combined_session(
            df_new_combined_bpm,
            df_new_combined_uterus
        )
    except Exception as e:
        error_msg = f"Ошибка при вычислении фич из объединённых данных: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)

    # - 10. Создание DataFrame для предсказания (на основе ВСЕХ данных) -
    data_for_prediction = pd.DataFrame({
        'mean_bpm': [mean_bpm],
        'std_bpm': [std_bpm],
        'mean_uterus': [mean_uterus],
        'std_uterus': [std_uterus], # Исправлена опечатка в названии колонки
        'anamnesis_score': [risk_level] # Используем переданный/глобальный mean_score
    })
    print(f"✅ Создан DataFrame для предсказания (на основе ВСЕХ накопленных данных):{data_for_prediction}")

    # - 11. Предсказание (на основе ВСЕХ данных) -
    try:
        # predict_proba возвращает массив вероятностей для каждого класса [[P(class=0), P(class=1)]]
        probability_of_hypoxia = model.predict_proba(data_for_prediction)[0][1] # Берем вероятность класса 1 (гипоксия)
        probability_percent = probability_of_hypoxia * 100
        print(f"🔮 Предсказанная вероятность гипоксии (на основе ВСЕХ накопленных данных): {probability_percent:.2f}%")
    except Exception as e:
        error_msg = f"Ошибка при предсказании моделью: {e}"
        print(error_msg)
        raise RuntimeError(error_msg)

    # - 12. Формирование результата (на основе ВСЕХ данных) -
    # Генерируем "отклонения", "диагнозы", "прогнозы" на основе фич и вероятности
    deviations = []
    diagnoses = []
    forecasts = []

    # --- Проверки на основе ВСЕХ накопленных данных ---
    if not np.isnan(mean_bpm):
        if mean_bpm > 180:
            # Тяжёлая тахикардия
            deviations.append("Тяжёлая тахикардия плода (ЧСС > 180 уд/мин)")

        elif mean_bpm < 100:
            # Тяжёлая брадикардия
            deviations.append("Тяжёлая брадикардия плода (ЧСС < 100 уд/мин)")


    if not np.isnan(std_bpm):
        if std_bpm < 5:
            # Низкая вариабельность
            deviations.append("Низкая вариабельность ЧСС плода (< 5 уд/мин)")


    if not np.isnan(mean_uterus):
        if mean_uterus > 50:  # Порог условный, зависит от данных
            # Высокая средняя активность (гипертонус?)
            deviations.append("Высокая средняя активность матки (> 50 у.е.)")


    # --- Прогнозы на основе вероятности гипоксии (probability_percent) ---
    if not np.isnan(probability_percent):  # На всякий случай проверим
        if probability_percent > 52:
            diagnoses.append(
                "Высокий риск развития гипоксии плода в ближайшие 30-60 минут. Требуется немедленное наблюдение.")
        elif probability_percent > 20:
            diagnoses.append(
                "Умеренный риск гипоксии плода. Рекомендуется усилить контроль и рассмотреть возможные вмешательства.")
        else:
            diagnoses.append("Низкий риск гипоксии плода на данный момент.")

    # - 13. Возврат результата -
    # Используем ЛОКАЛЬНЫЕ фичи в all_metrics
    return {
        "deviations": deviations,
        "diagnoses": diagnoses,
        "forecasts": forecasts,
        "all_metrics": (
            f"Средняя ЧСС : {mean_bpm_current:.2f} уд/мин\n"
            f"СКО ЧСС : {std_bpm_current:.2f} уд/мин\n"
            f"Средняя активность матки : {mean_uterus_current:.2f} у.е.\n"
            f"СКО активности матки : {std_uterus_current:.2f} у.е.\n"
        ),
        "probability_percent": probability_percent # Новая метрика: вероятность в процентах
    }


# --- Функция для сброса накопленных данных (опционально, для тестирования) ---
def reset_accumulated_data():
    """Сбрасывает накопленные данные, удаляя временные файлы."""
    try:
        if os.path.exists(COMBINED_BPM_PATH):
            os.remove(COMBINED_BPM_PATH)
            print(f"🗑️  Удалён временный файл: {COMBINED_BPM_PATH}")
        if os.path.exists(COMBINED_UTERUS_PATH):
            os.remove(COMBINED_UTERUS_PATH)
            print(f"🗑️  Удалён временный файл: {COMBINED_UTERUS_PATH}")
        # Удаляем папку temp, если она пуста
        if os.path.exists(TEMP_DIR) and not os.listdir(TEMP_DIR):
            os.rmdir(TEMP_DIR)
            print(f"🗑️  Удалена пустая директория: {TEMP_DIR}")
    except Exception as e:
        print(f"Ошибка при сбросе накопленных данных: {e}")

# --- Пример использования (если нужно тестировать отдельно) ---
# if __name__ == "__main__":
#     # Предположим, mean_score был установлен ранее
#     global mean_score
#     mean_score = 4.2 # Пример значения
#
#     # Сбросим накопленные данные перед тестом
#     reset_accumulated_data()
#
#     # Пути к первой паре файлов
#     bpm_path_1 = 'path/to/bpm_1.csv'
#     uterus_path_1 = 'path/to/uterus_1.csv'
#     file_paths_1 = [bpm_path_1, uterus_path_1]
#
#     try:
#         print("--- Обработка первой пары файлов ---")
#         result_1 = analyze_data(file_paths_1)
#         print("\n--- Результат анализа (1 пара) ---")
#         for key, value in result_1.items():
#             print(f"{key}: {value}")
#     except Exception as e:
#         print(f"Ошибка при обработке первой пары: {e}")
#
#     # Пути ко второй паре файлов
#     bpm_path_2 = 'path/to/bpm_2.csv'
#     uterus_path_2 = 'path/to/uterus_2.csv'
#     file_paths_2 = [bpm_path_2, uterus_path_2]
#
#     try:
#         print("\n--- Обработка второй пары файлов ---")
#         result_2 = analyze_data(file_paths_2)
#         print("\n--- Результат анализа (2 пары) ---")
#         for key, value in result_2.items():
#             print(f"{key}: {value}")
#     except Exception as e:
#         print(f"Ошибка при обработке второй пары: {e}")

