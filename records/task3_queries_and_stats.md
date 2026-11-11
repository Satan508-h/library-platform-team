# 检索与统计功能执行记录

- 执行时间：2026-11-11 17:50:44
- 数据量：books 50 / readers 30 / borrow_logs 3001

| # | 类型 | 功能 | 条件/管道要点 | 结果条数 |
|---|---|---|---|---|
| 1 | 检索 | 按类别 + 价格区间组合筛选（计算机，80—130 元） | `{"category": "计算机", "price": {"$gte": 80, "$lte": 130}}` | 6 |
| 2 | 检索 | 按标签多选匹配（$all: 编程 + 入门） | `{"tags": {"$all": ["编程", "入门"]}}` | 1 |
| 3 | 检索 | 按书名模糊检索（title 含 Python） | `{"title": {"$regex": "Python", "$options": "i"}}` | 2 |
| 4 | 检索 | 按出版年份范围检索（2020—2023） | `{"publish_date": {"$gte": "2020-01-01 00:00:00+00:00", "$lt": "2024-01-01 00:00:00+00:00"}}` | 9 |
| 5 | 检索 | 查询缺少 tags 字段的图书（数据质量核查） | `{"tags": {"$exists": false}}` | 4 |
| 6 | 检索 | 按评分排序取前 10（仅书名/作者/评分） | `{"sort": {"rating": -1}, "limit": 10, "projection": {"title": 1, "author": 1, "rating": 1}}` | 10 |
| 7 | 统计 | 按类别统计藏书量、平均价格、平均评分 | `{"$group": "category -> count/avg(price)/avg(rating)"}` | 6 |
| 8 | 统计 | 各学院借阅总量前 5（多集合 $lookup） | `{"$lookup": "readers", "$group": "college", "$limit": 5}` | 5 |
| 9 | 统计 | 按年月统计借阅趋势 | `{"$group": "year+month", "$sort": "year,month"}` | 38 |
| 10 | 统计 | 借阅次数最多的 10 本图书 + 馆藏位置 | `{"$sort": "borrow_count desc", "$limit": 10, "$project": "location.*"}` | 10 |
| 11 | 统计 | 分类统计结果写入 category_stats 集合 | `{"collection": "category_stats", "restored": "完全重建"}` | 6 |

## 关键结论

1. books 共 50 条，其中缺少 tags 字段 4 条，属于数据不齐的典型情况，用 $exists:false 可以精确筛出；
2. borrow_logs 共 3001 条，与源文件一致；
3. 分类统计结果已落入 category_stats 集合，后续查询与导出均基于该集合。