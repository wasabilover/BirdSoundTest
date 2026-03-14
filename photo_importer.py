"""
照片导入模块
负责从内存卡扫描并导入新照片
"""

import os
import shutil
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from config import (
    MEDIA_MOUNT_ROOT,
    CAMERA_PHOTO_DIRS,
    PHOTO_EXTENSIONS,
    BIRD_LIBRARY_DIR,
)

logger = logging.getLogger(__name__)


def find_memory_cards() -> List[str]:
    """扫描已挂载的内存卡/外部设备"""
    cards = []
    if not os.path.exists(MEDIA_MOUNT_ROOT):
        return cards

    for item in os.listdir(MEDIA_MOUNT_ROOT):
        volume_path = os.path.join(MEDIA_MOUNT_ROOT, item)
        if item.startswith(".") or not os.path.isdir(volume_path):
            continue
        # 跳过系统卷
        if item in ("Macintosh HD", "macOS", "Recovery", "Preboot", "VM", "Data"):
            continue
        # 检查是否有相机目录
        for cam_dir in CAMERA_PHOTO_DIRS:
            if os.path.exists(os.path.join(volume_path, cam_dir)):
                cards.append(volume_path)
                logger.info(f"发现内存卡/设备: {volume_path}")
                break

    return cards


def get_photo_date(photo_path: str) -> Optional[datetime]:
    """从 EXIF 信息读取拍摄日期，失败则用文件修改时间"""
    if HAS_PIEXIF and HAS_PIL:
        try:
            img = Image.open(photo_path)
            exif_data = img.info.get("exif", b"")
            if exif_data:
                exif_dict = piexif.load(exif_data)
                date_str = exif_dict.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal, None)
                if date_str:
                    if isinstance(date_str, bytes):
                        date_str = date_str.decode("utf-8")
                    return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        except Exception:
            pass
    # 退回文件修改时间
    try:
        ts = os.path.getmtime(photo_path)
        return datetime.fromtimestamp(ts)
    except Exception:
        return datetime.now()


def file_hash(path: str, block_size: int = 65536) -> str:
    """计算文件 MD5，用于去重"""
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            data = f.read(block_size)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def scan_photos_from_card(card_path: str) -> List[str]:
    """扫描内存卡上的所有照片"""
    photos = []
    scanned_dirs = set()

    # 先扫描相机标准目录
    for cam_dir in CAMERA_PHOTO_DIRS:
        full_dir = os.path.join(card_path, cam_dir)
        if os.path.exists(full_dir):
            scanned_dirs.add(os.path.realpath(full_dir))
            for root, _, files in os.walk(full_dir):
                for f in files:
                    if Path(f).suffix.lower() in PHOTO_EXTENSIONS:
                        photos.append(os.path.join(root, f))

    # 若没找到，全盘扫描（跳过系统目录）
    if not photos:
        for root, dirs, files in os.walk(card_path):
            # 跳过已扫描目录的重复
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if Path(f).suffix.lower() in PHOTO_EXTENSIONS:
                    photos.append(os.path.join(root, f))

    logger.info(f"从 {card_path} 扫描到 {len(photos)} 张照片")
    return photos


def import_photos(card_path: str, staging_dir: str) -> List[Tuple[str, datetime]]:
    """
    将内存卡照片导入到暂存目录
    返回: [(本地路径, 拍摄时间), ...]
    """
    os.makedirs(staging_dir, exist_ok=True)

    # 记录已有文件的hash，避免重复导入
    existing_hashes = set()
    for root, _, files in os.walk(staging_dir):
        for f in files:
            existing_hashes.add(file_hash(os.path.join(root, f)))

    photos_on_card = scan_photos_from_card(card_path)
    imported = []

    for src_path in photos_on_card:
        try:
            h = file_hash(src_path)
            if h in existing_hashes:
                logger.debug(f"跳过重复文件: {src_path}")
                continue

            photo_date = get_photo_date(src_path)
            # 用日期+原文件名组合，避免命名冲突
            date_str = photo_date.strftime("%Y%m%d_%H%M%S") if photo_date else "unknown"
            orig_name = Path(src_path).name
            dest_name = f"{date_str}_{orig_name}"
            dest_path = os.path.join(staging_dir, dest_name)

            # 若文件名冲突，加序号
            counter = 1
            while os.path.exists(dest_path):
                stem = Path(dest_name).stem
                suffix = Path(dest_name).suffix
                dest_path = os.path.join(staging_dir, f"{stem}_{counter}{suffix}")
                counter += 1

            shutil.copy2(src_path, dest_path)
            existing_hashes.add(h)
            imported.append((dest_path, photo_date))
            logger.info(f"已导入: {orig_name} -> {dest_name}")

        except Exception as e:
            logger.error(f"导入 {src_path} 失败: {e}")

    logger.info(f"本次共导入 {len(imported)} 张新照片")
    return imported
