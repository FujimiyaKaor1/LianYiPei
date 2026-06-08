# 链易配 — Git 团队协作管理方案

> 面向首次使用 Git 进行多人协同开发的团队  
> 仓库地址: https://github.com/FujimiyaKaor1/LianYiPei

---

## 一、仓库基本信息

| 项目 | 内容 |
|------|------|
| 仓库地址 | `https://github.com/FujimiyaKaor1/LianYiPei.git` |
| 主分支 | `main` |
| 开发分支 | `dev`（建议创建） |
| 当前提交数 | 1 (初始提交) |

---

## 二、Git 工作流：GitHub Flow（简化版）

推荐使用**最简分支策略**，适合小团队：

```
main (受保护，所有代码经过审核后合并)
  └── dev (日常开发集成)
        ├── feat/xxx (功能分支)
        ├── fix/xxx  (修复分支)
        └── docs/xxx (文档分支)
```

### 分支命名规范

```
feat/matching-llm-enhance    # 新功能
fix/port-5000-conflict       # Bug修复  
docs/git-collaboration       # 文档更新
refactor/matcher-engine      # 代码重构
```

---

## 三、新人首次克隆与配置（必读）

### Step 1: 克隆仓库

```bash
git clone https://github.com/FujimiyaKaor1/LianYiPei.git
cd LianYiPei
```

### Step 2: 配置 Git 身份（每人必做）

```bash
git config user.name "你的姓名"
git config user.email "你的邮箱@example.com"
```

### Step 3: 配置 Clash 代理（加速下载）

```bash
# 仅对 GitHub 设置代理，不影响其他网络
git config http.https://github.com.proxy http://127.0.0.1:7897
git config http.proxy http://127.0.0.1:7897
```

### Step 4: 复制环境配置

```bash
# 复制 .env 模板并修改本地密码
cp .env.example .env
# 编辑 .env，填入本地 MySQL 密码、Ollama 配置等
```

---

## 四、日常工作流（每次写代码的固定流程）

### 第1步：同步最新代码

```bash
# 切换到 dev 分支
git checkout dev
# 拉取最新代码
git pull origin dev
```

### 第2步：创建功能分支

```bash
# 从 dev 创建自己的分支
git checkout -b feat/你的功能名
```

### 第3步：写代码 + 小步提交

```bash
# 写完一个小功能后
git add .                           # 暂存所有改动
git commit -m "feat: 描述你做了什么"  # 提交

# 🔴 提交前务必检查：不要提交 .env 文件！
# .env 已在 .gitignore 中，正常情况下不会被提交
# 可用 git status 确认
```

### 第4步：推送到 GitHub

```bash
git push origin feat/你的功能名
```

### 第5步：在 GitHub 上创建 Pull Request (PR)

1. 访问 https://github.com/FujimiyaKaor1/LianYiPei
2. 点击 "Compare & pull request"
3. 设置 base: `dev` ← compare: `feat/你的功能名`
4. 填写 PR 描述，@ 队友审核
5. 审核通过后点击 "Merge pull request"

---

## 五、提交信息规范 (Conventional Commits)

```bash
# 格式: <type>: <简短描述>

feat: 新增绿色供应链优先匹配模式
fix: 修复端口5000在macOS上被占用的问题
docs: 更新启动说明文档
refactor: 重构匹配引擎评分计算逻辑
test: 补充预警引擎单元测试
style: 格式化代码缩进
chore: 更新依赖版本
```

---

## 六、常见场景处理

### 场景1: 队友更新了 dev，你需要同步

```bash
git checkout dev
git pull origin dev
git checkout feat/你的分支
git merge dev          # 将 dev 的最新代码合并到你的分支
# 如有冲突，解决后 git add . && git commit
```

### 场景2: 写了一半需要切分支

```bash
git stash              # 暂存当前未提交的改动
git checkout dev       # 切换分支
# ... 处理其他事情后回来
git checkout feat/你的分支
git stash pop          # 恢复之前的改动
```

### 场景3: 代码冲突怎么办

```bash
# 合并时出现 CONFLICT 提示
# 1. 打开冲突文件，找到 <<<<<<< ======= >>>>>>> 标记
# 2. 手动选择保留哪些代码
# 3. 删除冲突标记
# 4. git add 冲突文件
# 5. git commit
```

### 场景4: 不小心提交了 .env

```bash
# 如果还沒 push
git reset HEAD~1         # 撤销最近一次提交（保留文件改动）
# 或
git rm --cached .env     # 从 Git 跟踪中移除 .env
git commit -m "chore: 移除误提交的 .env"

# 如果已经 push 了
# 🔴 立即轮换 .env 中所有密钥！然后：
git rm --cached .env
git commit -m "chore: 移除 .env 并轮换密钥"
git push
```

---

## 七、禁止事项（重要！）

| 🚫 禁止 | 原因 |
|---------|------|
| **直接 push 到 main** | main 是受保护分支，只通过 PR 合并 |
| **提交 .env 文件** | 包含数据库密码和 API 密钥 |
| **git push --force** | 会覆盖队友的代码！ |
| **提交 venv/ 或 node_modules/** | 已在 .gitignore，体积巨大 |
| **提交 .DS_Store** | macOS 系统文件，已在 .gitignore |
| **在 main 上直接开发** | 始终从 dev 分支创建功能分支 |

---

## 八、环境差异处理

### Python 版本差异

- macOS: Python 3.13 (Apple Silicon)
- Windows: Python 3.9+
- **方案**: `requirements.txt` 使用 `>=` 版本约束，`SQLAlchemy>=2.0.36`

### 端口差异

- macOS: 端口 5000 被 AirPlay Receiver 占用 → 自动切换到 5050
- Windows: 端口 5000 通常可用
- **方案**: `run.py` 已内置自动端口检测

### 路径分隔符

- Windows: `\`
- macOS: `/`
- **方案**: 代码中使用 `pathlib.Path` 处理路径

---

## 九、Git 配置速查

```bash
# 查看当前配置
git config --list

# 查看远程仓库
git remote -v

# 查看分支
git branch -a

# 查看提交历史
git log --oneline -10

# 查看当前状态
git status

# 查看改动详情
git diff
```

---

## 十、团队协作建议

1. **每日站会前 git pull**：确保本地代码是最新的
2. **小步提交，频繁 push**：每次提交只做一件事，描述清晰
3. **功能分支存活不超过 2 天**：避免合并时巨大冲突
4. **PR 必须有人 review 后才能合并**：互相检查代码质量
5. **dev 分支保持随时可运行**：合并前本地先测试通过
6. **.env 绝不提交**：每次 git add 前用 `git status` 确认
