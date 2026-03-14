"""
观鸟助手主程序
整合所有模块，提供两种运行方式：
1. 自动监控模式（--watch）：持续监控内存卡插入，自动触发
2. 手动运行模式（默认）：扫描当前已挂载的内存卡，立即处理
"""

import os
import sys
import time
import logging
import argparse
import subprocess
from datetime import datetime
from typing import Optional

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# 导入各模块
from config import BIRD_LIBRARY_DIR, REPORT_OUTPUT_DIR, MEDIA_MOUNT_ROOT
from photo_importer import find_memory_cards, import_photos
from bird_identifier import identify_bird
from photo_archiver import archive_batch
from report_generator import generate_reports


STAGING_DIR = os.path.join(BIRD_LIBRARY_DIR, ".staging")
PROCESSED_CARDS = set()  # 本次运行中已处理过的卡


def print_banner():
    print("\n" + "=" * 60)
    print("  🦅  观鸟助手 Bird Watcher Assistant")
    print("      自动识别 · 智能归档 · 生成报告")
    print("=" * 60 + "\n")


def process_memory_card(card_path: str) -> bool:
    """
    完整处理一张内存卡：
    1. 导入照片到暂存目录
    2. AI 识别每张照片
    3. 按鸟类归档
    4. 生成报告
    """
    logger.info(f"\n{'─'*50}")
    logger.info(f"开始处理内存卡: {card_path}")
    logger.info(f"{'─'*50}")

    session_name = datetime.now().strftime("%Y%m%d_%H%M%S")
    card_staging = os.path.join(STAGING_DIR, session_name)

    # Step 1: 导入照片
    logger.info("📷 Step 1/4  扫描并导入照片...")
    imported = import_photos(card_path, card_staging)

    if not imported:
        logger.info("没有发现新照片，本次处理结束。")
        return False

    logger.info(f"✅ 导入完成，共 {len(imported)} 张新照片\n")

    # Step 2: AI 识别
    logger.info("🔍 Step 2/4  AI 识别鸟类（可能需要一些时间）...")
    bird_results = []
    for i, (photo_path, photo_date) in enumerate(imported, 1):
        photo_name = os.path.basename(photo_path)
        logger.info(f"  [{i}/{len(imported)}] 识别中: {photo_name}")
        result = identify_bird(photo_path)
        bird_results.append(result)
        logger.info(
            f"         → {result['name_cn']}"
            + (f" ({result['name_sci']})" if result.get("name_sci") and result["name_sci"] != "Unknown" else "")
            + f"  置信度: {result['confidence']:.0%}"
        )

    # 统计本次识别结果
    species_found = set(r["name_cn"] for r in bird_results if r["name_cn"] != "未识别")
    logger.info(f"\n✅ 识别完成，发现 {len(species_found)} 种鸟类: {', '.join(sorted(species_found))}\n")

    # Step 3: 归档
    logger.info("📁 Step 3/4  按鸟类归档照片...")
    session_records = archive_batch(
        photos=imported,
        bird_results=bird_results,
        session_name=session_name,
    )
    logger.info(f"✅ 归档完成，照片已整理到: {BIRD_LIBRARY_DIR}\n")

    # Step 4: 生成报告
    logger.info("📊 Step 4/4  生成观鸟报告...")
    report_paths = generate_reports(session_records, session_name)

    logger.info(f"\n{'='*50}")
    logger.info("🎉 全部处理完成！")
    if "excel" in report_paths:
        logger.info(f"   📊 Excel 报告: {report_paths['excel']}")
    if "image" in report_paths:
        logger.info(f"   🖼️  图片海报: {report_paths['image']}")
    logger.info(f"{'='*50}\n")

    # macOS 通知
    _send_notification(
        title="🦅 观鸟助手",
        message=f"处理完成！发现 {len(species_found)} 种鸟类，{len(session_records)} 张照片已归档",
    )

    # 在 Finder 中打开报告目录
    if report_paths:
        subprocess.run(["open", REPORT_OUTPUT_DIR], check=False)

    return True


def _send_notification(title: str, message: str):
    """发送 macOS 系统通知"""
    try:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    except Exception:
        pass


def _get_mounted_volumes():
    """获取当前已挂载的设备列表"""
    if not os.path.exists(MEDIA_MOUNT_ROOT):
        return set()
    return {
        item for item in os.listdir(MEDIA_MOUNT_ROOT)
        if not item.startswith(".")
           and os.path.isdir(os.path.join(MEDIA_MOUNT_ROOT, item))
           and item not in ("Macintosh HD", "macOS", "Recovery", "Preboot", "VM", "Data")
    }


def run_watch_mode():
    """
    持续监控模式：每 5 秒检查一次是否有新内存卡插入
    """
    print_banner()
    logger.info("👁️  进入监控模式，请插入内存卡...")
    logger.info(f"   监控路径: {MEDIA_MOUNT_ROOT}")
    logger.info("   按 Ctrl+C 退出\n")

    known_volumes = _get_mounted_volumes()

    try:
        while True:
            current_volumes = _get_mounted_volumes()
            new_volumes = current_volumes - known_volumes

            if new_volumes:
                logger.info(f"检测到新设备: {new_volumes}")
                time.sleep(2)  # 等待挂载完成

                cards = find_memory_cards()
                for card in cards:
                    card_id = os.path.basename(card)
                    if card_id not in PROCESSED_CARDS:
                        PROCESSED_CARDS.add(card_id)
                        process_memory_card(card)
                    else:
                        logger.info(f"卡 {card_id} 已在本次运行中处理过，跳过")

            known_volumes = current_volumes
            time.sleep(5)

    except KeyboardInterrupt:
        logger.info("\n已退出监控模式。")


def run_once():
    """
    单次运行模式：扫描当前已挂载的内存卡并处理
    """
    print_banner()
    logger.info("🔍 扫描已挂载的内存卡...")

    cards = find_memory_cards()
    if not cards:
        logger.warning("未发现内存卡。请确保内存卡已插入并挂载。")
        logger.info(f"（扫描路径: {MEDIA_MOUNT_ROOT}）")
        return

    logger.info(f"发现 {len(cards)} 个内存卡: {[os.path.basename(c) for c in cards]}")
    for card in cards:
        process_memory_card(card)


def run_demo():
    """
    演示模式：用本地文件夹中的照片模拟内存卡，测试完整流程
    """
    print_banner()
    logger.info("🎮 演示模式：请输入一个包含鸟类照片的文件夹路径")
    demo_dir = input("照片文件夹路径 (直接回车使用 ~/Pictures): ").strip()
    if not demo_dir:
        demo_dir = os.path.expanduser("~/Pictures")

    if not os.path.exists(demo_dir):
        logger.error(f"路径不存在: {demo_dir}")
        return

    # 临时设置 MEDIA_MOUNT_ROOT 为 demo_dir 的父目录
    import config
    original_root = config.MEDIA_MOUNT_ROOT
    config.MEDIA_MOUNT_ROOT = os.path.dirname(demo_dir)

    import photo_importer
    photo_importer.MEDIA_MOUNT_ROOT = config.MEDIA_MOUNT_ROOT

    # 直接当作内存卡路径处理（不经过 find_memory_cards）
    session_name = datetime.now().strftime("%Y%m%d_%H%M%S")
    card_staging = os.path.join(STAGING_DIR, session_name)

    from photo_importer import scan_photos_from_card, get_photo_date
    import shutil

    logger.info(f"扫描照片: {demo_dir}")

    # 直接扫描所有照片
    from pathlib import Path
    from config import PHOTO_EXTENSIONS
    photos_in_dir = [
        os.path.join(root, f)
        for root, _, files in os.walk(demo_dir)
        for f in files
        if Path(f).suffix.lower() in PHOTO_EXTENSIONS
    ]

    if not photos_in_dir:
        logger.warning("该文件夹中没有找到支持的照片格式。")
        logger.info(f"支持格式: {PHOTO_EXTENSIONS}")
        return

    # 复制到暂存目录
    os.makedirs(card_staging, exist_ok=True)
    imported = []
    for src in photos_in_dir[:20]:  # 演示最多处理20张
        dest = os.path.join(card_staging, os.path.basename(src))
        shutil.copy2(src, dest)
        imported.append((dest, get_photo_date(src)))

    logger.info(f"导入 {len(imported)} 张照片进行演示")

    # 识别 + 归档 + 报告
    bird_results = []
    for i, (photo_path, photo_date) in enumerate(imported, 1):
        logger.info(f"  [{i}/{len(imported)}] 识别中: {os.path.basename(photo_path)}")
        result = identify_bird(photo_path)
        bird_results.append(result)
        logger.info(f"         → {result['name_cn']} ({result['confidence']:.0%})")

    session_records = archive_batch(imported, bird_results, session_name)
    report_paths = generate_reports(session_records, session_name)

    logger.info("\n✅ 演示完成！")
    for k, v in report_paths.items():
        logger.info(f"   {k}: {v}")

    if report_paths:
        subprocess.run(["open", REPORT_OUTPUT_DIR], check=False)


def main():
    parser = argparse.ArgumentParser(
        description="🦅 观鸟助手 - 自动识别鸟类、归档照片、生成报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用方式:
  python main.py              # 扫描当前已挂载的内存卡（单次）
  python main.py --watch      # 持续监控，插卡自动触发
  python main.py --demo       # 演示模式，使用本地照片测试
        """,
    )
    parser.add_argument("--watch", action="store_true", help="持续监控内存卡插入")
    parser.add_argument("--demo", action="store_true", help="演示模式（使用本地照片）")
    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.watch:
        run_watch_mode()
    else:
        run_once()


if __name__ == "__main__":
    main()
