import os
from pathlib import Path

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 精确定位上传目录
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

print(BASE_DIR)