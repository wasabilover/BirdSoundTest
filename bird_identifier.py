"""
鸟类识别模块
优先使用本地 YOLOv8 分类模型（无需网络，专为深圳雀形目优化）
备用：iNaturalist Vision API / 腾讯云图像分析
"""

import os
import json
import base64
import logging
import re
import time
from pathlib import Path
from typing import Optional, Dict

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from PIL import Image
    import io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from config import (
    TENCENT_SECRET_ID,
    TENCENT_SECRET_KEY,
    TENCENT_REGION,
    USE_INATURALIST,
    INATURALIST_USERNAME,
    INATURALIST_PASSWORD,
    INATURALIST_APP_ID,
    INATURALIST_APP_SECRET,
    LOCAL_MODEL_PATH,
    LOCAL_MODEL_CONFIDENCE,
    USE_LOCAL_MODEL,
)

logger = logging.getLogger(__name__)

# 缓存 iNaturalist access token（进程级）
_INAT_TOKEN_CACHE: dict = {"token": None, "expires": 0}

# 缓存本地模型实例（进程级，避免重复加载）
_LOCAL_MODEL_CACHE: dict = {"model": None, "path": None}

# iNaturalist 常见鸟类中英文映射
BIRD_NAME_MAP = {
    "Passer montanus": "麻雀",
    "Hirundo rustica": "家燕",
    "Cyanopica cyanus": "灰喜鹊",
    "Pica pica": "喜鹊",
    "Corvus macrorhynchos": "大嘴乌鸦",
    "Turdus merula": "乌鸫",
    "Alcedo atthis": "普通翠鸟",
    "Ardea cinerea": "苍鹭",
    "Egretta garzetta": "小白鹭",
    "Ardea alba": "大白鹭",
    "Motacilla alba": "白鹡鸰",
    "Acridotheres cristatellus": "八哥",
    "Garrulax canorus": "画眉",
    "Orthotomus sutorius": "长尾缝叶莺",
    "Parus major": "大山雀",
}


# ============================================================
# 本地 YOLOv8 模型识别
# ============================================================

def _load_local_model():
    """加载本地 YOLOv8 分类模型（延迟加载，进程内缓存）"""
    if _LOCAL_MODEL_CACHE["model"] is not None and _LOCAL_MODEL_CACHE["path"] == LOCAL_MODEL_PATH:
        return _LOCAL_MODEL_CACHE["model"]

    model_path = Path(LOCAL_MODEL_PATH)
    if not model_path.exists():
        logger.warning(f"本地模型文件不存在: {LOCAL_MODEL_PATH}")
        return None

    try:
        from ultralytics import YOLO
        model = YOLO(str(model_path))
        _LOCAL_MODEL_CACHE["model"] = model
        _LOCAL_MODEL_CACHE["path"] = LOCAL_MODEL_PATH
        logger.info(f"本地模型加载成功: {LOCAL_MODEL_PATH}")
        return model
    except Exception as e:
        logger.error(f"本地模型加载失败: {e}")
        return None


def identify_with_local_model(image_path: str) -> Optional[Dict]:
    """
    使用本地 YOLOv8 分类模型识别鸟类（深圳雀形目专用）
    返回: {"name_cn": "白头鹎", "confidence": 0.95, "source": "LocalModel"}
    """
    if not USE_LOCAL_MODEL:
        return None

    model = _load_local_model()
    if model is None:
        return None

    try:
        results = model.predict(
            source=image_path,
            device="cpu",
            verbose=False,
            imgsz=224,
        )
        if not results:
            return None

        result = results[0]
        probs = result.probs  # 分类概率

        top1_idx = probs.top1
        top1_conf = float(probs.top1conf)
        class_name = result.names[top1_idx]  # 类别名（中文）

        if top1_conf < LOCAL_MODEL_CONFIDENCE:
            logger.info(f"本地模型置信度过低 ({top1_conf:.1%})，结果: {class_name}")
            return {
                "name_cn": "未识别",
                "name_sci": "Unknown",
                "confidence": round(top1_conf, 3),
                "source": "LocalModel",
                "folder_name": "未识别",
            }

        # Top-5 候选（用于日志）
        top5_indices = probs.top5
        top5_confs = probs.top5conf.tolist()
        top5 = [(result.names[i], round(float(c), 3)) for i, c in zip(top5_indices, top5_confs)]
        logger.info(f"本地模型 Top5: {top5}")

        return {
            "name_cn": class_name,
            "name_sci": "",   # 本地模型只有中文类名
            "confidence": round(top1_conf, 3),
            "source": "LocalModel",
            "top5": top5,
        }

    except Exception as e:
        logger.warning(f"本地模型推理失败: {e}")
        return None


# ============================================================
# iNaturalist API
# ============================================================

def resize_image_for_api(image_path: str, max_size: int = 1024) -> bytes:
    """将图片压缩后转为bytes，用于API上传"""
    if HAS_PIL:
        img = Image.open(image_path)
        img.thumbnail((max_size, max_size), Image.LANCZOS)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    else:
        with open(image_path, "rb") as f:
            return f.read()


def _get_inat_token() -> Optional[str]:
    """通过 iNaturalist OAuth 密码流获取 access_token"""
    if not (INATURALIST_USERNAME and INATURALIST_PASSWORD):
        return None
    if not HAS_REQUESTS:
        return None

    # 检查缓存
    if _INAT_TOKEN_CACHE["token"] and time.time() < _INAT_TOKEN_CACHE["expires"]:
        return _INAT_TOKEN_CACHE["token"]

    try:
        resp = requests.post(
            "https://www.inaturalist.org/oauth/token",
            data={
                "client_id": INATURALIST_APP_ID,
                "client_secret": INATURALIST_APP_SECRET,
                "grant_type": "password",
                "username": INATURALIST_USERNAME,
                "password": INATURALIST_PASSWORD,
            },
            timeout=15,
            headers={"User-Agent": "BirdWatcherApp/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        expires_in = data.get("expires_in", 86400)
        _INAT_TOKEN_CACHE["token"] = token
        _INAT_TOKEN_CACHE["expires"] = time.time() + expires_in - 60
        logger.info("iNaturalist token 获取成功")
        return token
    except Exception as e:
        logger.warning(f"iNaturalist 获取 token 失败: {e}")
        return None


def identify_with_inaturalist(image_path: str) -> Optional[Dict]:
    """使用 iNaturalist Vision API 识别物种（需要账号）"""
    if not HAS_REQUESTS or not USE_INATURALIST:
        return None

    token = _get_inat_token()
    if not token:
        return None

    try:
        img_bytes = resize_image_for_api(image_path, max_size=800)
        files = {"image": ("photo.jpg", img_bytes, "image/jpeg")}
        url = "https://api.inaturalist.org/v1/computervision/score_image"
        headers = {
            "User-Agent": "BirdWatcherApp/1.0",
            "Authorization": f"Bearer {token}",
        }

        resp = requests.post(url, files=files, timeout=30, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        for item in results:
            taxon = item.get("taxon", {})
            ancestor_ids = taxon.get("ancestor_ids", [])
            if 3 in ancestor_ids or taxon.get("id") == 3:
                name_sci = taxon.get("name", "Unknown")
                name_cn = (
                    taxon.get("preferred_common_name", "")
                    or BIRD_NAME_MAP.get(name_sci, "")
                    or _extract_cn_name(taxon)
                    or name_sci
                )
                score = item.get("combined_score", 0)
                return {
                    "name_cn": name_cn,
                    "name_sci": name_sci,
                    "confidence": round(score, 3),
                    "source": "iNaturalist",
                }

        if results:
            taxon = results[0].get("taxon", {})
            name_sci = taxon.get("name", "Unknown")
            name_cn = taxon.get("preferred_common_name", "") or BIRD_NAME_MAP.get(name_sci, name_sci)
            return {
                "name_cn": name_cn,
                "name_sci": name_sci,
                "confidence": round(results[0].get("combined_score", 0), 3),
                "source": "iNaturalist",
            }

    except Exception as e:
        logger.warning(f"iNaturalist 识别失败: {e}")

    return None


def _extract_cn_name(taxon: dict) -> str:
    """从 taxon 的 names 字段里找中文名"""
    for name_item in taxon.get("names", []):
        if name_item.get("locale", "") in ("zh", "zh-CN", "zh-TW"):
            return name_item.get("name", "")
    return ""


# ============================================================
# 腾讯云 API
# ============================================================

def identify_with_tencent(image_path: str) -> Optional[Dict]:
    """使用腾讯云图像分析识别鸟类（备用）"""
    if not (TENCENT_SECRET_ID and TENCENT_SECRET_KEY):
        return None
    if not HAS_REQUESTS:
        return None

    try:
        import hmac
        import hashlib
        from datetime import datetime, timezone

        img_bytes = resize_image_for_api(image_path, max_size=1024)
        img_b64 = base64.b64encode(img_bytes).decode()

        service = "tiia"
        host = "tiia.tencentcloudapi.com"
        action = "DetectLabel"
        version = "2019-05-29"
        payload = json.dumps({"ImageBase64": img_b64, "Scenes": ["CAMERA"]})
        timestamp = int(time.time())
        date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")

        canonical_headers = f"content-type:application/json\nhost:{host}\n"
        signed_headers = "content-type;host"
        hashed_payload = hashlib.sha256(payload.encode()).hexdigest()
        canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"
        credential_scope = f"{date}/{service}/tc3_request"
        hashed_cr = hashlib.sha256(canonical_request.encode()).hexdigest()
        string_to_sign = f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{hashed_cr}"

        def sign(key, msg):
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        secret_date = sign(f"TC3{TENCENT_SECRET_KEY}".encode(), date)
        secret_service = sign(secret_date, service)
        secret_signing = sign(secret_service, "tc3_request")
        signature = hmac.new(secret_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

        authorization = (
            f"TC3-HMAC-SHA256 Credential={TENCENT_SECRET_ID}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json",
            "Host": host,
            "X-TC-Action": action,
            "X-TC-Version": version,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Region": TENCENT_REGION,
        }

        resp = requests.post(f"https://{host}", headers=headers, data=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        labels = data.get("Response", {}).get("Labels", [])
        for label in labels:
            if "鸟" in label.get("Name", "") or "禽" in label.get("Name", ""):
                return {
                    "name_cn": label["Name"],
                    "name_sci": "",
                    "confidence": label.get("Confidence", 0) / 100.0,
                    "source": "TencentCloud",
                }

    except Exception as e:
        logger.warning(f"腾讯云识别失败: {e}")

    return None


# ============================================================
# 主识别函数
# ============================================================

def identify_bird(image_path: str, retry: int = 2) -> Dict:
    """
    主识别函数，优先使用本地模型，备用网络API
    识别顺序：本地YOLOv8模型 → iNaturalist → 腾讯云
    返回: {
        "name_cn": "白头鹎",
        "name_sci": "",
        "confidence": 0.95,
        "source": "LocalModel",
        "folder_name": "白头鹎"
    }
    """
    result = None

    # 1. 优先本地模型（无需网络，最快）
    if USE_LOCAL_MODEL:
        result = identify_with_local_model(image_path)
        if result and result.get("name_cn") != "未识别":
            _fill_folder_name(result)
            logger.info(
                f"[本地模型] {result['name_cn']} "
                f"置信度={result.get('confidence', 0):.1%}"
            )
            return result

    # 2. iNaturalist（网络备用）
    has_inat = bool(USE_INATURALIST and INATURALIST_USERNAME and INATURALIST_PASSWORD)
    has_tencent = bool(TENCENT_SECRET_ID and TENCENT_SECRET_KEY)

    for attempt in range(retry):
        if has_inat and not result:
            result = identify_with_inaturalist(image_path)
        if not result and has_tencent:
            result = identify_with_tencent(image_path)
        if result:
            break
        if attempt < retry - 1:
            time.sleep(1)

    if not result:
        logger.warning(f"无法识别: {image_path}，归入「未识别」文件夹")
        return {
            "name_cn": "未识别",
            "name_sci": "Unknown",
            "confidence": 0.0,
            "source": "none",
            "folder_name": "未识别",
        }

    _fill_folder_name(result)
    logger.info(
        f"[{result.get('source','-')}] {result['name_cn']} "
        f"({result.get('name_sci','')}) "
        f"置信度={result.get('confidence', 0):.1%}"
    )
    return result


def _fill_folder_name(result: Dict) -> None:
    """生成规范的归档文件夹名（就地修改 result 字典）"""
    name_cn = result.get("name_cn", "") or result.get("name_sci", "未知鸟类")
    name_sci = result.get("name_sci", "")
    safe_cn = re.sub(r'[\\/:*?"<>|]', "_", name_cn)
    safe_sci = re.sub(r'[\\/:*?"<>|]', "_", name_sci)

    if safe_sci and safe_sci != safe_cn and safe_sci not in ("Unknown", ""):
        result["folder_name"] = f"{safe_cn} ({safe_sci})"
    else:
        result["folder_name"] = safe_cn
