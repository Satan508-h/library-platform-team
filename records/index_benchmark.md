# 索引优化前后对比（benchmark_index.py 自动生成）

- 生成时间：2026-11-11 18:18:28
- 每项查询重复执行：200 次（放大实验 20 次），取平均 / 中位数 / P95
- 扫描量取自 explain(executionStats) 的 totalDocsExamined / totalKeysExamined

| 查询场景 | 索引 | 前：扫描方式 | 前：扫描文档 | 前：平均耗时(ms) | 后：扫描方式 | 后：扫描文档 | 后：平均耗时(ms) | 耗时提速 | 扫描量下降 |
|---|---|---|---|---|---|---|---|---|---|
| books：类别 + 价格区间（50 条） | idx_category_price | COLLSCAN | 50 | 0.809 | IXSCAN | 6 | 0.861 | 0.94x | 8.3x |
| borrow_logs：按读者取流水并倒序（3000 条） | idx_reader_date | COLLSCAN | 3000 | 1.949 | IXSCAN | 10 | 0.850 | 2.29x | 300.0x |
| borrow_logs：时间范围 + 倒序（3000 条） | idx_borrow_date | COLLSCAN | 3000 | 2.096 | IXSCAN | 10 | 0.866 | 2.42x | 300.0x |
| bench_borrow：按读者 + 倒序（200,000 条放大实验） | idx_bench_reader_date | COLLSCAN | 200000 | 40.625 | IXSCAN | 10 | 0.831 | 48.89x | 20000.0x |

结论：
1. 建立索引后扫描方式由 COLLSCAN 变为 IXSCAN，扫描文档数下降到与命中结果同量级；
2. 50 条与 3000 条的集合规模太小，绝对耗时为亚毫秒级，耗时差异受缓存与噪声影响；
3. 因此在 200,000 条的 bench_borrow 上放大验证，索引带来的耗时差异才稳定可观测；
4. 排序场景（borrow_date 倒序）在无索引时会额外出现 SORT 阶段，属于内存排序，数据量增长后最先出问题。