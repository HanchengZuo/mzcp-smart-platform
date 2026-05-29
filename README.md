# 民主测评管理系统

一个 Vue + Flask 的民主测评管理系统雏形，支持 root 管理基础资料、创建测评表并分配给巡察组；巡察组生成不同人员层级的二维码；被测评人员扫码提交；root 和巡察组查看任务进度与统计分析。

## 当前功能

- root 默认账号：`root`，默认密码：`root123`
- 单位管理：创建民主测评对应的单位
- 单位删除保护：已经挂载测评表的单位不能删除
- 测评人员层级管理：预设 A/B/C 层级，也可新增并拖动排序
- 巡察组管理：创建巡察组登录账号，root 可查看和修改账号密码；已有任务的账号不能删除
- 时间任务：按上半年、下半年创建填报周期
- 测评表单：为单位选择时间任务、巡察组，配置任意数量测评选项和权重
- 合并单元格式表单：按“测评维度 + 子项”设计，例如“政治建设”下挂多个具体测评项
- 二维码填报：巡察组按层级生成专属填报链接和二维码，并维护目标人数
- 自动统计：展示全表、维度和每个小项的选项数量与满意度
- 任务进度：root 跟踪所有巡察组任务进度；巡察组查看自己的任务进度和填报数据
- 数据库迁移：使用 Flask-Migrate/Alembic 管理表结构版本，Docker 部署默认使用 PostgreSQL

## 本地开发

后端：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python wsgi.py
```

前端：

```bash
cd frontend
npm install
npm run dev
```

访问前端：`http://localhost:5173`

后端健康检查：`http://localhost:5001/api/health`

## Docker 运行

```bash
cp .env.example .env
docker compose up --build
```

访问：`http://localhost:8080`

如果本机 8080 已被占用，可以临时换端口：

```bash
FRONTEND_PORT=8081 docker compose up --build
```

Docker Compose 会启动 PostgreSQL，后端启动时自动执行：

```bash
flask --app wsgi:app db upgrade
flask --app wsgi:app seed-data
```

## 数据库迁移

后续调整表结构时：

```bash
cd backend
source .venv/bin/activate
flask --app wsgi:app db migrate -m "describe schema change"
flask --app wsgi:app db upgrade
```

生产环境不要手工改表，优先提交迁移文件并通过发布流程执行 `db upgrade`。

## Git

项目已初始化 git 仓库。常用命令：

```bash
git status
git add .
git commit -m "Initial democratic evaluation platform"
```
