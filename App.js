import React, { useState, useEffect } from 'react';

const App = () => {
  const [anamnesis, setAnamnesis] = useState('');
  const [showAnamnesisInput, setShowAnamnesisInput] = useState(true);
  const [diagResult, setDiagResult] = useState(null);
  const [bpmFiles, setBpmFiles] = useState([]);
  const [uterusFiles, setUterusFiles] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [results, setResults] = useState([]);
  const [currentIdx, setCurrentIdx] = useState(0);

  // Текущий результат — вычисляется из results и currentIdx
  const currentResult = results[currentIdx]?.result || null;

  const handleAnamnesisSubmit = async (e) => {
    e.preventDefault();
    if (!anamnesis.trim()) return;

    setIsLoading(true);

    try {
      const response = await fetch('/api/diagnose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ anamnesis }),
      });

      const data = await response.json();
      console.log("Ответ от /api/diagnose:", data);
      setDiagResult(data);
      setShowAnamnesisInput(false);
    } catch (error) {
      console.error('Ошибка при вызове /api/diagnose:', error);
      alert('Ошибка при обработке анамнеза. Пожалуйста, попробуйте снова.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleBpmUpload = (event) => {
    const selected = Array.from(event.target.files);
    setBpmFiles(selected);
  };

  const handleUterusUpload = (event) => {
    const selected = Array.from(event.target.files);
    setUterusFiles(selected);
  };

  const startAnalysis = async () => {
    if (bpmFiles.length === 0 || uterusFiles.length === 0) {
      alert('❌ Загрузите файлы в обе папки.');
      return;
    }

    if (bpmFiles.length !== uterusFiles.length) {
      alert(`❌ Количество файлов в папках не совпадает.\nBPM: ${bpmFiles.length}, Uterus: ${uterusFiles.length}.\nПожалуйста, загрузите одинаковое количество файлов.`);
      // Удаляем все файлы
      setBpmFiles([]);
      setUterusFiles([]);
      return;
    }

    setIsLoading(true);
    setIsStreaming(true);
    setResults([]);
    setCurrentIdx(0);

    const formData = new FormData();
    bpmFiles.forEach(file => formData.append('bpm_files', file));
    uterusFiles.forEach(file => formData.append('uterus_files', file));

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      console.log("Ответ от /api/analyze:", data);

      if (data.error) {
        alert(`❌ Ошибка от сервера: ${data.error}`);
        setIsLoading(false);
        // Удаляем файлы, если была ошибка
        setBpmFiles([]);
        setUterusFiles([]);
        return;
      }

      // ✅ НАЧИНАЕМ ОПРАШИВАТЬ /api/results КАЖДЫЕ 1 СЕКУНДУ — ПОКА НЕ ПОЛУЧИМ ВСЁ
      const poll = setInterval(async () => {
        try {
          const res = await fetch('/api/results');
          const data = await res.json();

          if (data.error) return;

          console.log("Опрос /api/results:", data);

          // Если все результаты готовы — останавливаем поллинг
          if (data.is_complete && data.total_processed > 0) {
            setResults(data.results);
            clearInterval(poll);
            setIsLoading(false);
          }
        } catch (err) {
          console.error('Polling error:', err);
        }
      }, 1000);

    } catch (error) {
      console.error('Upload error:', error);
      setIsLoading(false);
      setIsStreaming(false);
      setResults([{
        result: {
          deviations: [],
          diagnoses: [],
          forecasts: ["Ошибка при обработке данных. Пожалуйста, попробуйте позже."],
          all_metrics: "Ошибка подключения к серверу анализа"
        }
      }]);
      // Удаляем файлы, если была ошибка
      setBpmFiles([]);
      setUterusFiles([]);
    }
  };

  // ✅ Фронтенд сам показывает результаты по одному — каждые 10 секунд
  useEffect(() => {
    if (results.length === 0 || !isStreaming) return;

    const interval = setInterval(() => {
      setCurrentIdx(prev => {
        const next = prev + 1;
        if (next >= results.length) {
          clearInterval(interval);
          setIsStreaming(false);
          return prev;
        }
        return next;
      });
    }, 3000);

    return () => clearInterval(interval);
  }, [results, isStreaming]);

  const resetAnalysis = () => {
    setIsStreaming(false);
    setResults([]);
    setCurrentIdx(0);
    setBpmFiles([]);
    setUterusFiles([]);
    setShowAnamnesisInput(true); // ✅ Возвращаем к вводу анамнеза
    setAnamnesis('');
    setDiagResult(null);
  };

  if (showAnamnesisInput) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-emerald-900 to-slate-900 text-white flex items-center justify-center p-6">
        <div className="bg-white/10 backdrop-blur-xl rounded-3xl border border-white/30 p-12 max-w-2xl w-full text-center">
          <h1 className="text-3xl md:text-4xl font-bold text-white mb-6">
            Сервис предиктивной аналитики физиологических данных
          </h1>
          <p className="text-lg text-emerald-200 mb-8">
            Для начала анализа введите анамнез пациентки
          </p>
          <form onSubmit={handleAnamnesisSubmit}>
            <textarea
              value={anamnesis}
              onChange={(e) => setAnamnesis(e.target.value)}
              placeholder="Введите анамнез пациентки..."
              className="w-full h-40 p-4 rounded-xl bg-slate-800/60 border border-emerald-400/60 text-white placeholder-emerald-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
            />
            <button
              type="submit"
              disabled={!anamnesis.trim() || isLoading}
              className={`mt-6 w-full py-4 rounded-2xl font-semibold transition-all duration-300 transform ${
                anamnesis.trim() && !isLoading
                  ? 'bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white shadow-xl border border-white/30'
                  : 'bg-gray-600 text-gray-400 cursor-not-allowed'
              }`}
            >
              {isLoading ? 'Обработка...' : 'Продолжить'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-900 to-slate-900 text-white overflow-hidden">
      {/* Фоновая ЭКГ-линия */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        <svg className="absolute bottom-0 left-0 w-full h-64 opacity-20" viewBox="0 0 1200 200" preserveAspectRatio="none">
          <path
            d="M0,100
               C100,50 200,150 300,100
               C400,50 500,150 600,100
               C700,50 800,150 900,100
               C1000,50 1100,150 1200,100
               L1200,200 L0,200 Z"
            fill="none"
            stroke="#059669"
            strokeWidth="4"
            strokeDasharray="20,10"
            strokeDashoffset="0"
          />
        </svg>
      </div>

      {/* Плавающая кнопка сброса */}
      {results.length > 0 && (
        <button
          onClick={resetAnalysis}
          className="fixed bottom-8 right-8 w-16 h-16 bg-white text-emerald-800 rounded-full shadow-2xl flex items-center justify-center transition-all duration-300 transform hover:scale-110 z-50 border-2 border-emerald-300/60"
          aria-label="Загрузить новые данные"
        >
          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
          </svg>
        </button>
      )}

      <div className="relative z-10 px-6 py-12">
        <div className="max-w-4xl mx-auto">
          {/* Заголовок */}
          <div className="text-center mb-12">
            <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
              Сервис предиктивной аналитики физиологических данных
            </h1>
            <p className="text-lg text-emerald-200 max-w-3xl mx-auto leading-relaxed">
              Интеллектуальный анализ данных для раннего выявления рисков у матери и плода
            </p>
          </div>

          {/* Кнопки загрузки */}
          {results.length === 0 && (
            <div className="bg-white/10 backdrop-blur-xl rounded-3xl border border-white/30 p-12 text-center hover:shadow-2xl transition-all duration-500 transform hover:-translate-y-1">
              <div className="mb-8 flex justify-center">
                <div className="w-20 h-20 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center border border-white/40">
                  <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                  </svg>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
                {/* Загрузка BPM */}
                <div>
                  <h3 className="text-xl font-semibold text-white mb-4">Загрузка данных BPM</h3>
                  <input
                    type="file"
                    id="bpm-upload"
                    className="hidden"
                    multiple
                    onChange={handleBpmUpload}
                    accept=".csv,.json,.txt,.dat"
                  />
                  <button
                    onClick={() => document.getElementById('bpm-upload').click()}
                    className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white font-semibold py-3 px-8 rounded-2xl transition-all duration-300 transform hover:scale-105 shadow-xl border border-white/30"
                  >
                    Загрузить данные BPM
                  </button>
                  {bpmFiles.length > 0 && (
                    <p className="mt-2 text-white">
                      Выбрано файлов: {bpmFiles.length}
                    </p>
                  )}
                </div>

                {/* Загрузка Uterus */}
                <div>
                  <h3 className="text-xl font-semibold text-white mb-4">Загрузка данных Uterus</h3>
                  <input
                    type="file"
                    id="uterus-upload"
                    className="hidden"
                    multiple
                    onChange={handleUterusUpload}
                    accept=".csv,.json,.txt,.dat"
                  />
                  <button
                    onClick={() => document.getElementById('uterus-upload').click()}
                    className="bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-white font-semibold py-3 px-8 rounded-2xl transition-all duration-300 transform hover:scale-105 shadow-xl border border-white/30"
                  >
                    Загрузить данные Uterus
                  </button>
                  {uterusFiles.length > 0 && (
                    <p className="mt-2 text-white">
                      Выбрано файлов: {uterusFiles.length}
                    </p>
                  )}
                </div>
              </div>

              {/* Кнопка запуска анализа */}
              <button
                onClick={startAnalysis}
                disabled={bpmFiles.length === 0 || uterusFiles.length === 0 || isLoading}
                className={`py-4 px-12 rounded-2xl font-semibold transition-all duration-300 transform ${
                  bpmFiles.length > 0 && uterusFiles.length > 0 && !isLoading
                    ? 'bg-gradient-to-r from-purple-500 to-purple-600 hover:from-purple-600 hover:to-purple-700 text-white shadow-xl border border-white/30'
                    : 'bg-gray-600 text-gray-400 cursor-not-allowed'
                }`}
              >
                {isLoading ? 'Обработка...' : 'Запустить анализ'}
              </button>

              <p className="mt-6 text-sm text-emerald-200">
              </p>
              <p className="mt-2 text-sm text-emerald-300">
                Загрузите одинаковое количество файлов в обе папки.
              </p>
            </div>
          )}

          {/* Индикатор потоковой обработки */}
          {isStreaming && (
            <div className="fixed top-4 left-1/2 transform -translate-x-1/2 bg-emerald-600 text-white px-6 py-2 rounded-full text-sm z-40 shadow-lg animate-pulse">
              🔴 Потоковая обработка
            </div>
          )}

          {/* Результаты анализа */}
          {results.length > 0 && (
            <div className="space-y-8">
              {/* Заголовок результатов */}
              <div className="text-center">
                <h2 className="text-3xl font-bold text-white">Результаты анализа</h2>
                <p className="text-emerald-300 mt-2">
                </p>
                <div className="w-24 h-1 bg-gradient-to-r from-emerald-400 to-emerald-500 mx-auto mt-4 rounded-full"></div>
              </div>

              {isLoading || (currentResult?.status === "received") ? (
                <div className="flex flex-col items-center justify-center py-16">
                  <p className="text-white text-lg font-medium">
                    {currentResult?.status === "received"
                      ? "Файлы сохранены. Генерирую прогнозы..."
                      : "Обрабатываю данные..."}
                  </p>
                </div>
              ) : (
                <>
                  {/* --- НОВОЕ: Окно риска гипоксии в стиле других блоков --- */}
                  {(() => {
                    const prob = currentResult?.probability_percent;
                    // Если вероятность не определена, не отображаем блок
                    if (prob === undefined) return null;
                    let bgColorClass = "";
                    let borderColorClass = "";
                    let iconColorClass = "";
                    let title = "";
                    let description = "";
                    if (prob < 20) {
                      // Зелёный стиль
                      bgColorClass = "from-green-900/40 to-green-800/30";
                      borderColorClass = "border-green-500";
                      iconColorClass = "text-green-400";
                      title = "Низкий риск гипоксии";
                      description = "Шанс гипоксии крайне мал";
                    } else if (prob > 52) {
                      // Красный стиль
                      bgColorClass = "from-red-900/40 to-red-800/30";
                      borderColorClass = "border-red-500";
                      iconColorClass = "text-red-400";
                      title = "Высокий риск гипоксии";
                      description = "Шанс гипоксии крайне высокий";
                    } else {
                      // Жёлтый стиль для 20-52%
                      bgColorClass = "from-amber-900/40 to-amber-800/30";
                      borderColorClass = "border-amber-500";
                      iconColorClass = "text-amber-400";
                      title = "Повышенный риск гипоксии";
                      // Пересчет в шкалу 1-100: ((prob - 20) / (52 - 20)) * (100 - 1) + 1
                      const level = Math.round(((prob - 20) / 32) * 99 + 1);
                      description = `Уровень проблемы: ${level}%`;
                    }
                    return (
                      <div
                        className={`bg-gradient-to-br ${bgColorClass} backdrop-blur-sm border-2 rounded-2xl p-8 shadow-lg transition-all duration-500 transform ${borderColorClass}`}
                      >
                        <h2 className="text-2xl font-bold text-white mb-6 flex items-center">
                          <svg className={`w-6 h-6 mr-2 ${iconColorClass}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
                          </svg>
                          {title}
                        </h2>
                        <div className="bg-gradient-to-r from-white/10 to-white/5 backdrop-blur-xs border border-white/20 rounded-xl p-6 shadow-lg">
                          <p className="text-white text-center text-xl font-semibold">
                            {description}
                          </p>
                        </div>
                      </div>
                    );
                  })()}
                  {/* --- КОНЕЦ НОВОГО: Окно риска гипоксии --- */}

                  {/* Удален блок "Отсутствуют отклонения от нормы" */}

                  {/* Блок A: Отклонения от нормы (отображается только если есть отклонения) */}
                  {currentResult?.deviations && currentResult.deviations.length > 0 && (
                    <div
                      className="bg-gradient-to-br from-red-900/40 to-red-800/30 backdrop-blur-sm border-2 rounded-2xl p-8 shadow-lg transition-all duration-500 transform"
                      style={{ borderColor: '#EF4444' }}
                    >
                      <h2 className="text-2xl font-bold text-white mb-6 flex items-center">
                        <svg className="w-6 h-6 mr-2 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                        </svg>
                        Отклонения от нормы
                      </h2>
                      <ul className="space-y-3">
                        {currentResult.deviations.map((deviation, index) => (
                          <li
                            key={index}
                            className="bg-gradient-to-r from-red-800/60 to-red-700/50 backdrop-blur-xs border border-red-400/60 rounded-xl p-4 shadow-lg text-white hover:shadow-xl hover:scale-[1.01] transition-all duration-200"
                          >
                            <div className="flex items-start">
                              <div className="w-2 h-2 bg-red-400 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                              <span className="text-sm">{deviation}</span>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Блок B: Возможные диагнозы */}
                  {currentResult?.diagnoses && currentResult.diagnoses.length > 0 && (
                    <div
                      className="bg-gradient-to-br from-amber-900/40 to-amber-800/30 backdrop-blur-sm border-2 rounded-2xl p-8 shadow-lg transition-all duration-500 transform"
                      style={{ borderColor: '#F59E0B' }}
                    >
                      <h2 className="text-2xl font-bold text-white mb-6 flex items-center">
                        <svg className="w-6 h-6 mr-2 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
                        </svg>
                        Рекомендации
                      </h2>
                      <ul className="space-y-3">
                        {currentResult.diagnoses.map((diagnosis, index) => (
                          <li
                            key={index}
                            className="bg-gradient-to-r from-amber-800/60 to-amber-700/50 backdrop-blur-xs border border-amber-400/60 rounded-xl p-4 shadow-lg text-white hover:shadow-xl hover:scale-[1.01] transition-all duration-200"
                          >
                            <div className="flex items-start">
                              <div className="w-2 h-2 bg-amber-400 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                              <span className="text-sm">{diagnosis}</span>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* УДАЛЕН БЛОК C: Прогнозы возможных отклонений */}

                  {/* Блок D: Все показатели */}
                  <div
                    className="bg-gradient-to-br from-slate-900/40 to-slate-800/30 backdrop-blur-sm border-2 rounded-2xl p-8 shadow-lg transition-all duration-500 transform"
                    style={{ borderColor: '#9CA3AF' }}
                  >
                    <h2 className="text-2xl font-bold text-white mb-6 flex items-center">
                      <svg className="w-6 h-6 mr-2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                      </svg>
                      Все показатели
                    </h2>
                    <div className="bg-gradient-to-r from-slate-800/60 to-slate-700/50 backdrop-blur-xs border border-slate-400/60 rounded-xl p-6 shadow-lg">
                      {/* ✅ Отображение risk_score, если есть */}
                      {currentResult?.risk_score !== undefined && (
                        <div className="mb-4 p-3 bg-amber-900/50 rounded-lg">
                          <strong className="text-amber-300">Средний риск гипоксии по анамнезу:</strong> {currentResult.risk_score.toFixed(2)}
                        </div>
                      )}
                      <pre className="whitespace-pre-wrap text-slate-200 text-sm font-mono leading-relaxed">
                        {currentResult?.all_metrics || "Нет данных"}
                      </pre>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Футер */}
          <div className="text-center mt-16 text-emerald-200 text-sm">
            <p>© 2025 Сервис предиктивной аналитики физиологических данных. Решение разработано для интеграции с фетальными мониторами.</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default App;
