# 智慧图书馆数字资源平台 · 交付总览

本目录是《NoSQL数据库技术与应用（第2版）》期末项目的完整交付物，全部在本机 Docker 中真实运行过（2026-11-11）。

## 目录导航

| 目录 | 内容 |
|---|---|
| `app/` | 16 个 Python 源文件：配置与连接、业务管理、初始化导入、功能菜单、索引基准、权限验证、副本集工具、分片检查 |
| `config/` | `config.json`：single / replicaset / sharded 三种部署形态的连接串、账号、GridFS 配置 |
| `deploy/` | 3 个 compose 文件：`compose.single.yml`、`compose.replicaset.yml`、`compose.shard.yml` |
| `data/` | 自定义数据目录（bind mount 到容器）：single、rs1—rs4、cfg、shard1、shard2 |
| `scripts/` | 运维与产出脚本：故障演练编排、记录汇总、结果导出、截图渲染、文档生成 |
| `records/` | 24 份运行日志与汇总（索引基准、权限矩阵、故障转移时间线与探针、节点增删、分片状态） |
| `exports/` | 8 个统计结果 CSV + `overview.json` + `downloaded/`（GridFS 下载校验副本） |
| `docs/` | 项目文档（Word）、答辩材料、验收对照清单、46 张截图（38 张运行日志 + 8 张 Compass 真机）、集合结构图 |
| `logs/` | 运行期辅助日志 |

## 三种部署形态

```text
单机      lib-mongo-single          127.0.0.1:27018   --auth --directoryperdb
副本集    lib-rs1 / rs2 / rs3       27101—27103       rs=librs，keyFile，priority 2:1:1
分片集群  lib-cfg / shard1 / shard2 / mongos
                                  27201 / 27301 / 27302 / 27030
应用容器  lib-app（python:3.12-slim，网络 libnet，挂载本目录）
```

启动与运行：

```powershell
docker compose -f deploy/compose.single.yml up -d
python app/init_db.py --reset
python app/import_data.py
python app/main.py --demo

# 副本集 / 分片集群内的命令需在 lib-app 中执行
docker exec -e WISELIB_PROFILE=replicaset lib-app python app/ha_tools.py status
docker exec -e WISELIB_PROFILE=sharded   lib-app python app/shard_check.py
```

## 关键实测结果

| 指标 | 结果 |
|---|---|
| 数据规模 | books 50 / readers 30 / borrow_logs 3000（37 个月，2023-01—2025-12） |
| 索引 | 16 个；流水按读者查询扫描文档 3000→10，放大 20 万条提速 48.89 倍 |
| 权限 | 只读 6 类操作被拒、读写仅写与查询、管理全部通过（单机与分片一致） |
| GridFS | 6 个文件，按书名下载字节级校验全部一致 |
| 故障转移 | 停止主节点后 ≤1 秒完成选主，179 次探针读写零失败，原主按优先级回归 |
| 节点增删 | 3→4→3 成员，term 不变，未触发重新选举 |
| 分片 | 哈希分片 1300 : 1700（43.3% : 56.7%），4 块均分；定向 0.71 ms vs 跨分片 1.50 ms |

## 环境安全

未触碰本机原有 `mongodb` 容器（0.0.0.0:27017）与 `xbla-*`、`sfly-*` 两套业务容器；本项目全部实例新建容器、新建网络 `libnet`，端口只绑 `127.0.0.1`。

## 待补项

- 项目文档封面学号为占位（`＿＿＿＿＿＿＿＿`），请填写本人学号。
- 图形化核对已用 MongoDB Compass 1.50.0 完成（单机实例），截图见 `docs/截图/compass_01`—`compass_08`；副本集与分片形态的容器名在宿主机不可解析，其证据为容器内 mongosh 输出。
