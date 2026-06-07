"""
一键灌库入口（项目根目录）：

  python seed_data.py              # 全量种子（含演示看板）
  python seed_data.py --reset      # 清空后全量
  python seed_data.py --demo-boards-only  # 仅追加演示看板（需已有企业数据）

等价于：python scripts/seed_data.py [参数...]
"""
from __future__ import annotations

import os
import subprocess
import sys

if __name__ == "__main__":
    script = os.path.join(os.path.dirname(__file__), "scripts", "seed_data.py")
    raise SystemExit(subprocess.call([sys.executable, script, *sys.argv[1:]]))
