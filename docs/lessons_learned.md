# Career Engine - 已知坑点与经验 (Lessons Learned)

> 在构建过程中踩过的坑，供后续维护参考。

## SQLite / 数据库

1. **CHECK 约束内禁止注释**: `CHECK(col IN ('a', -- comment 'b'))` 会导致 `near ")": syntax error`。SQL 的 `--` 注释会吃掉后面的括号。
   - ✅ 正确: `CHECK(col IN ('a', 'b'))`
   - ❌ 错误: `CHECK(col IN ('a', -- 选项A 'b'))`

2. **DDL 批量执行验证**: 20+ 条 DDL 放在列表里 `for ddl in DDL: conn.execute(ddl)`，任何一条语法错误都会让整个 init 失败，且报错不指明是哪一条。
   - 开发时先逐条 enumerate 验证: `for i, ddl in enumerate(DDL): try... except...`
   - 确认全通过后再部署

3. **DB_PATH 层级计算**: 深层嵌套模块中 `os.path.dirname(__file__)` 的次数必须与文件层级匹配。
   - `core/database/models.py` 需 3 次 dirname 才到 skill 根目录
   - 建议各模块统一用 `SKILL_DIR` 常量，不要各自算

## Python 字符串

4. **`str.format()` 占位符不含 `/`**: `{company_culture/product}` 报 `KeyError`，因为 `/` 不是合法 Python 标识符。
   - ✅ `{company_culture}`
   - ❌ `{company_culture/product}`

## 模块导入

5. **`__init__.py` 不可省略**: 每个子目录 (`core/`, `core/database/`, `core/scoring/` 等) 必须有 `__init__.py`，否则 `sys.path.insert` 后 `from core.xxx` 报 `ModuleNotFoundError`。

## Skill 构建模式

6. **分阶段验证**: 数据库模型 → 评分引擎 → CLI 入口 → 全链路测试。每阶段验证通过再继续，避免错误累积。
7. **测试数据与生产数据分离**: 测试用的 profile/skills 用独立脚本创建，不污染交互流程。
