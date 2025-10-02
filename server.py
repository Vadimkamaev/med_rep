from flask import Flask, request, jsonify
import os
import threading
import shutil
from analytics_module import analyze_data, diagnoz_analyze

app = Flask(__name__)

# ✅ Две временные папки
BPM_DIR = '/tmp/predictive_analytics_bpm'
UTERUS_DIR = '/tmp/predictive_analytics_uterus'
os.makedirs(BPM_DIR, exist_ok=True)
os.makedirs(UTERUS_DIR, exist_ok=True)

# ✅ КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: ИНИЦИАЛИЗИРУЕМ ГЛОБАЛЬНО
results_list = []  # ← ДОЛЖЕН БЫТЬ ЗДЕСЬ, В КОРНЕ
is_processing = False

@app.route('/api/diagnose', methods=['POST'])
def diagnose():
    data = request.get_json()
    anamnesis = data.get('anamnesis', '')

    try:
        result = diagnoz_analyze([], anamnesis)  # diagnoz_analyze не требует файлов
        return jsonify(result)
    except Exception as e:
        print(f"❌ Ошибка в diagnoz_analyze: {e}")
        return jsonify({
            "deviations": [],
            "diagnoses": [],
            "forecasts": ["Ошибка при анализе анамнеза."],
            "all_metrics": f"Ошибка: {str(e)}"
        }), 500

@app.route('/api/analyze', methods=['POST'])
def analyze():
    global is_processing, results_list

    if 'bpm_files' not in request.files or 'uterus_files' not in request.files:
        return jsonify({'error': 'No files uploaded for bpm or uterus'}), 400

    bpm_files = request.files.getlist('bpm_files')
    uterus_files = request.files.getlist('uterus_files')

    if not bpm_files or not uterus_files:
        return jsonify({'error': 'No files selected for bpm or uterus'}), 400

    if len(bpm_files) != len(uterus_files):
        # ✅ УДАЛЯЕМ ВСЕ ФАЙЛЫ В ОБЕИХ ПАПКАХ
        for d in [BPM_DIR, UTERUS_DIR]:
            for f in os.listdir(d):
                os.remove(os.path.join(d, f))
        return jsonify({'error': f'Количество файлов не совпадает: bpm = {len(bpm_files)}, uterus = {len(uterus_files)}'}), 400

    # ✅ ОЧИЩАЕМ ПАПКИ — КАЖДАЯ НОВАЯ СЕССИЯ
    for d in [BPM_DIR, UTERUS_DIR]:
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))

    # Сохраняем файлы в соответствующие папки
    for file in bpm_files:
        if file.filename == '':
            continue
        filepath = os.path.join(BPM_DIR, file.filename)
        file.save(filepath)
        print(f"💾 Сохранён файл bpm: {filepath}")

    for file in uterus_files:
        if file.filename == '':
            continue
        filepath = os.path.join(UTERUS_DIR, file.filename)
        file.save(filepath)
        print(f"💾 Сохранён файл uterus: {filepath}")

    # ✅ ОЧИЩАЕМ РЕЗУЛЬТАТЫ ПРЕДЫДУЩЕЙ СЕССИИ
    results_list = []

    # Запускаем фоновую обработку
    if not is_processing:
        is_processing = True
        threading.Thread(target=process_files_background, daemon=True).start()

    return jsonify({
        "status": "received",
        "message": "Файлы сохранены. Обрабатываю данные...",
        "total_pairs": len(bpm_files)
    }), 200

def process_files_background():
    global is_processing, results_list

    bpm_files = sorted([f for f in os.listdir(BPM_DIR) if not f.startswith('.')])
    uterus_files = sorted([f for f in os.listdir(UTERUS_DIR) if not f.startswith('.')])

    if not bpm_files or not uterus_files or len(bpm_files) != len(uterus_files):
        print("❌ Нарушено количество файлов при обработке.")
        is_processing = False
        return

    print(f"▶️ Начинаю обработку {len(bpm_files)} пар файлов...")

    for i in range(len(bpm_files)):
        bpm_file = bpm_files[i]
        uterus_file = uterus_files[i]
        bpm_path = os.path.join(BPM_DIR, bpm_file)
        uterus_path = os.path.join(UTERUS_DIR, uterus_file)

        print(f"🔄 Обрабатываю пару {i+1}/{len(bpm_files)}: {bpm_file} и {uterus_file}")

        try:
            result = analyze_data([bpm_path, uterus_path])
        except Exception as e:
            print(f"❌ Ошибка в analyze_data для пары {bpm_file} и {uterus_file}: {e}")
            result = {
                "deviations": [f"Ошибка анализа: {str(e)}"],
                "diagnoses": [],
                "forecasts": [],
                "all_metrics": "Ошибка в обработке данных"
            }

        # ✅ ДОБАВЛЯЕМ РЕЗУЛЬТАТ В ГЛОБАЛЬНЫЙ СПИСОК
        results_list.append({
            "file_pair": f"{bpm_file} и {uterus_file}",
            "result": result,
            "index": i + 1
        })

        print(f"✅ Результат #{i+1} добавлен. Всего: {len(results_list)}")

    is_processing = False
    print("🏁 Обработка завершена. Все результаты готовы.")

@app.route('/api/results', methods=['GET'])
def get_all_results():
    # ✅ ВОЗВРАЩАЕМ ВСЕ РЕЗУЛЬТАТЫ — ДАЖЕ ЕСЛИ ПРОЦЕСС НЕ ЗАВЕРШЁН
    return jsonify({
        "results": results_list,
        "is_complete": not is_processing,
        "total_processed": len(results_list),
        "total_expected": len(results_list)
    }), 200

@app.route('/api/result/latest', methods=['GET'])
def get_latest_result():
    if not results_list:
        return jsonify({"error": "Нет данных"}), 404
    return jsonify(results_list[-1]["result"]), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)