"""
照片归档模块
根据识别结果将照片移动到对应鸟类子文件夹
"""

import os
import shutil
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional

from config import BIRD_LIBRARY_DIR

logger = logging.getLogger(__name__)

# 记录文件，保存所有识别历史
RECORD_FILE = os.path.join(BIRD_LIBRARY_DIR, ".bird_records.json")


def load_records() -> List[Dict]:
    """加载历史观鸟记录"""
    if os.path.exists(RECORD_FILE):
        try:
            with open(RECORD_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_records(records: List[Dict]):
    """保存观鸟记录"""
    os.makedirs(BIRD_LIBRARY_DIR, exist_ok=True)
    with open(RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def archive_photo(
    photo_path: str,
    bird_info: Dict,
    photo_date: Optional[datetime] = None,
) -> Tuple[str, Dict]:
    """
    将照片归档到对应鸟类文件夹
    返回: (归档后的路径, 记录条目)
    """
    folder_name = bird_info.get("folder_name", "未识别")
    target_dir = os.path.join(BIRD_LIBRARY_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)

    # 按年月再建子目录
    if photo_date:
        year_month = photo_date.strftime("%Y-%m")
        target_dir = os.path.join(target_dir, year_month)
        os.makedirs(target_dir, exist_ok=True)

    orig_name = Path(photo_path).name
    dest_path = os.path.join(target_dir, orig_name)

    # 文件名冲突处理
    counter = 1
    while os.path.exists(dest_path):
        stem = Path(orig_name).stem
        suffix = Path(orig_name).suffix
        dest_path = os.path.join(target_dir, f"{stem}_{counter}{suffix}")
        counter += 1

    shutil.move(photo_path, dest_path)
    logger.info(f"归档: {orig_name} -> {folder_name}/{Path(dest_path).name}")

    # 构建记录条目
    record = {
        "file": dest_path,
        "original_name": orig_name,
        "bird_cn": bird_info.get("name_cn", "未识别"),
        "bird_sci": bird_info.get("name_sci", ""),
        "confidence": bird_info.get("confidence", 0),
        "source": bird_info.get("source", ""),
        "date": photo_date.isoformat() if photo_date else datetime.now().isoformat(),
        "folder": folder_name,
        "archived_at": datetime.now().isoformat(),
    }
    return dest_path, record


def archive_batch(
    photos: List[Tuple[str, datetime]],
    bird_results: List[Dict],
    session_name: Optional[str] = None,
) -> List[Dict]:
    """
    批量归档照片
    photos: [(photo_path, shoot_date), ...]
    bird_results: [bird_info_dict, ...]
    返回: 本次归档的记录列表
    """
    records = load_records()
    session_records = []

    for (photo_path, photo_date), bird_info in zip(photos, bird_results):
        try:
            dest_path, record = archive_photo(photo_path, bird_info, photo_date)
            if session_name:
                record["session"] = session_name
            session_records.append(record)
            records.append(record)
        except Exception as e:
            logger.error(f"归档 {photo_path} 失败: {e}")

    save_records(records)
    logger.info(f"本次归档完成，共 {len(session_records)} 张照片")
    return session_records


def get_library_stats() -> Dict:
    """统计鸟类库概况"""
    records = load_records()
    stats = {
        "total_photos": len(records),
        "total_species": 0,
        "species_list": {},
    }
    for r in records:
        name = r.get("bird_cn", "未识别")
        if name not in stats["species_list"]:
            stats["species_list"][name] = {
                "count": 0,
                "sci_name": r.get("bird_sci", ""),
                "photos": [],
            }
        stats["species_list"][name]["count"] += 1
        stats["species_list"][name]["photos"].append(r.get("file", ""))
    stats["total_species"] = len(stats["species_list"])
    return stats
