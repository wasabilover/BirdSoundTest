"""
观鸟助手 - 配置文件
在这里设置你的个人参数
"""

import os

# ============================================================
# 基础路径设置
# ============================================================

# 观鸟照片的总归档目录（按鸟类分子文件夹）
BIRD_LIBRARY_DIR = os.path.expanduser("~/Pictures/BirdLibrary")

# 报告输出目录
REPORT_OUTPUT_DIR = os.path.expanduser("~/Pictures/BirdReports")

# 内存卡挂载的根路径（macOS 默认挂载在 /Volumes/）
MEDIA_MOUNT_ROOT = "/Volumes"

# 内存卡上照片所在的相对路径（常见相机目录）
CAMERA_PHOTO_DIRS = [
    "DCIM",
    "dcim",
    "DCIM/100CANON",
    "DCIM/100NIKON",
    "DCIM/100OLYMP",
    "DCIM/100MSDCF",
    "DCIM/100PHOTO",
]

# 支持的照片格式
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".raw", ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2"}

# ============================================================
# AI 识别设置
# ============================================================

# ── 本地 YOLOv8 分类模型（首选，无需网络）────────────────────
# 训练完成后自动生成，路径可在 train_classifier.py 运行后查看
LOCAL_MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "runs", "shenzhen_passerines_v1", "weights", "best.pt"
)
# 本地模型置信度阈值（低于此值归入「未识别」）
LOCAL_MODEL_CONFIDENCE = 0.5
# 是否启用本地模型（推荐 True）
USE_LOCAL_MODEL = True

# ── iNaturalist（推荐，免费注册，识别准确率最高）──────────────
# 注册地址: https://www.inaturalist.org/signup
# 注册后在此填入账号密码，程序会自动获取 token
INATURALIST_USERNAME = "terryoy"   # 你的 iNaturalist 用户名
INATURALIST_PASSWORD = "m0ntypyth0n"   # 你的 iNaturalist 密码
# iNaturalist OAuth App（使用官方默认即可，无需自建）
INATURALIST_APP_ID = "us.inaturalist.iphone"
INATURALIST_APP_SECRET = "secret"
USE_INATURALIST = True

# ── 腾讯云（备用，需开通图像分析服务）────────────────────────
# 前往 https://console.cloud.tencent.com/tiia 开通后填入
TENCENT_SECRET_ID = ""   # 替换为你的 SecretId
TENCENT_SECRET_KEY = ""  # 替换为你的 SecretKey
TENCENT_REGION = "ap-guangzhou"

# ============================================================
# 报告设置
# ============================================================

# 报告中每行显示几张鸟类缩略图
REPORT_COLS = 3

# 缩略图大小（宽 x 高，像素）
THUMBNAIL_SIZE = (300, 250)

# 报告标题
REPORT_TITLE = "观鸟记录报告"

# 你的观鸟者名字（会显示在报告里）
OBSERVER_NAME = "观鸟爱好者"
