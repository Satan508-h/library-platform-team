﻿# 故障转移演练编排脚本（PowerShell），逐条记录时间点
# 用法：powershell -NoProfile -File scripts\failover_drill.ps1
$root = "C:\Users\33879\Desktop\期末项目-智慧图书馆数字资源平台-学生包\智慧图书馆平台-实现交付"
$timeline = Join-Path $root "records\task5_5_failover_timeline.log"
$watch = "/work/智慧图书馆平台-实现交付/records/task5_5_watch.log"
$probeOut = "/work/智慧图书馆平台-实现交付/records/task5_5_probe_stdout.log"

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    "$ts  $msg" | Out-File -FilePath $timeline -Append -Encoding utf8
    Write-Host "$ts  $msg"
}

function Snapshot {
    # 单次快照：watch 0 0 只输出一行
    $line = docker exec -e WISELIB_PROFILE=replicaset lib-app python app/ha_tools.py watch 0 0
    Log "  $line"
    return $line
}

if (Test-Path -LiteralPath $timeline) { Remove-Item -LiteralPath $timeline -Force }
Log "演练开始：启动持续读写探针（90 秒）与状态轮询（100 秒，1 秒间隔）"

docker exec -d -e WISELIB_PROFILE=replicaset lib-app sh -c "python app/ha_tools.py probe 90 > $probeOut 2>&1"
docker exec -d -e WISELIB_PROFILE=replicaset lib-app sh -c "python app/ha_tools.py watch 100 1 > $watch 2>&1"

Start-Sleep -Seconds 12
Log "STEP0 基线状态（停止主节点前）"
Snapshot | Out-Null

Log "STEP1 停止当前主节点容器 lib-rs1（模拟主节点宕机）"
docker stop lib-rs1 | Out-Null
Log "lib-rs1 已停止"

$found = $false
for ($i = 1; $i -le 15; $i++) {
    Start-Sleep -Seconds 2
    $line = Snapshot
    if ($line -match "primary=lib-rs2" -or $line -match "primary=lib-rs3") {
        Log "STEP2 检测到新主节点：$line"
        $found = $true
        break
    }
}
if (-not $found) { Log "STEP2 失败：30 秒内未检测到新主节点" }

Start-Sleep -Seconds 6
Log "STEP3 重启原主节点 lib-rs1，观察其角色"
docker start lib-rs1 | Out-Null
for ($i = 1; $i -le 8; $i++) {
    Start-Sleep -Seconds 3
    Snapshot | Out-Null
}
Log "STEP4 演练结束，等待探针写完"
Start-Sleep -Seconds 15
Log "完成"
