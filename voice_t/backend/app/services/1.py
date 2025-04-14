import os
import sys

# 获取当前目录并添加CosyVoice路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COSYVOICE_PATH = os.path.join(ROOT_DIR, "cosyvoice")
sys.path.append(ROOT_DIR)
sys.path.append('{}/third_party/Matcha-TTS'.format(ROOT_DIR))
from app.core.config import settings
print(COSYVOICE_PATH)


model_dir = settings.MODELS_DIR
if os.path.exists(COSYVOICE_PATH):
    sys.path.append(ROOT_DIR)
    # 尝试导入CosyVoice
    try:
        from cosyvoice.cli.cosyvoice import CosyVoice, CosyVoice2
        from cosyvoice.utils.file_utils import load_wav, logging
        from cosyvoice.utils.common import set_all_random_seed
        COSYVOICE_AVAILABLE = True
        print("CosyVoice 模块加载成功")
    except ImportError as e:
        print(f"导入 CosyVoice 失败: {e}")
        COSYVOICE_AVAILABLE = False

VOICE_DB_PATH = os.path.join(settings.UPLOAD_DIR, "voice_library.json")
print(VOICE_DB_PATH)