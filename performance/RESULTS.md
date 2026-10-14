# Результаты Gatling, 2026-10-14

Все пять профилей прошли с нулём ошибок HTTP и lifecycle-групп. Приоритеты сохранялись 1..N, итоговое число задач — 10 на команду. 11 регрессионных тестов прошли без пропусков.

| Команд | Пользователей | Gatling RPS | Gatling TPS | HTTP p95, мс | JVM live max* | Heap used max*, MiB | RSS max*, MiB |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 20 | 335.41 | 83.85 | 107 | 40 | 99.8 | 365.4 |
| 10 | 20 | 439.08 | 109.77 | 96 | 46 | 97.9 | 371.8 |
| 100 | 20 | 466.62 | 116.66 | 93 | 47 | 94.7 | 354.8 |
| 1000 | 20 | 520.33 | 130.08 | 90 | 47 | 88.1 | 382.5 |
| 1000 | 100 | 431.67 | 107.92 | 526 | 131 | 106.3 | 426.9 |

* Максимумы памяти и live threads получены из выборочных замеров внутри фактического HTTP-интервала, а не из непрерывного поиска lifetime peak. Пользователи, Java threads и OS threads — разные показатели. Heap used не равен RSS.

Для каждого профиля: 10 исходных задач на команду, 30 секунд прогрева отдельно от 60 секунд измерения. API: 2 CPU, container limit 1 GiB, Xms256m/Xmx512m, NMT summary и JFR. PostgreSQL имеет отдельный лимит 2 CPU/1 GiB. Gatling работает на том же Windows-host; это инструментированные локальные одиночные прогоны.

RPS/TPS и процентили в таблице взяты из native Gatling stats.js, поэтому совпадают с HTML-отчётами. Точные rates по HTTP-временному интервалу сохранены отдельно в summary.json. TPS — завершённый сценарий из четырёх HTTP-запросов, не SQL-транзакции.

При 1000 командах рост с 20 до 100 пользователей повысил HTTP p95 и число потоков, но снизил throughput. Это наблюдение данного ограниченного runtime, а не доказательство конкретной причины или production capacity. Полная диагностика оптимизации — отдельная задача.

- [HTML-сравнение и артефакты](results/20261014-gatling/index.html)
- [Native Gatling на 1000 команд / 100 пользователей](results/20261014-gatling/teams-1000-users-100/measurement/index.html)
- [Сводный JSON](results/20261014-gatling/summary.json)
- [Воспроизведение и определения](README.md)

Сохранены JFR, class histogram, thread/heap/NMT snapshots до/во время/после, native-memory diff, metrics CSV/JSONL, footprint процесса Gatling и PostgreSQL, PNG/SVG-графики, raw binary Gatling logs, warmup reports и JUnit XML. Временные smoke/build-copy/plot dependency папки удалены; старый Python-generator удалён, его измерения оставлены только в historical/. Benchmark-контейнеры остановлены без удаления volume; обычное приложение не изменено.
