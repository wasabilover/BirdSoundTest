"""
深圳雀形目分类模型训练脚本
使用 YOLOv8n-cls，基于 /Users/terryoy/Desktop/雀形目识别员 数据集
"""
import os
import sys
from pathlib import Path
from ultralytics import YOLO

# ===== 配置 =====
DATASET_DIR = "/Users/terryoy/Desktop/雀形目识别员"
PRETRAINED_MODEL = "/Users/terryoy/Desktop/yolov8n-cls.pt"
PROJECT_DIR = "/Users/terryoy/WorkBuddy/20260313210102/bird_watcher/runs"
RUN_NAME = "shenzhen_passerines_v1"

EPOCHS = 150
IMG_SIZE = 224
BATCH_SIZE = 16
PATIENCE = 30   # 早停：30轮没提升就停


def check_dataset(dataset_dir):
    """检查数据集结构"""
    train_dir = Path(dataset_dir) / "train"
    val_dir = Path(dataset_dir) / "val"

    if not train_dir.exists():
        print(f"错误：训练集不存在 -> {train_dir}")
        sys.exit(1)

    classes = sorted([d.name for d in train_dir.iterdir() if d.is_dir()])
    print(f"\n数据集检查：")
    print(f"  路径：{dataset_dir}")
    print(f"  类别数：{len(classes)}")
    print(f"\n各类别样本数（训练/验证）：")

    total_train = 0
    total_val = 0
    for cls in classes:
        train_count = len(list((train_dir / cls).glob("*.*")))
        val_count = len(list((val_dir / cls).glob("*.*"))) if (val_dir / cls).exists() else 0
        print(f"  {cls:<20} 训练:{train_count:>3}  验证:{val_count:>2}")
        total_train += train_count
        total_val += val_count

    print(f"\n  合计：训练 {total_train} 张，验证 {total_val} 张")
    return classes


def train():
    print("=" * 60)
    print("  深圳雀形目分类模型训练")
    print("=" * 60)

    # 检查数据集
    classes = check_dataset(DATASET_DIR)

    # 检查预训练模型
    if not Path(PRETRAINED_MODEL).exists():
        print(f"\n未找到预训练模型 {PRETRAINED_MODEL}，将使用 yolov8n-cls.pt（自动下载）")
        model_path = "yolov8n-cls.pt"
    else:
        model_path = PRETRAINED_MODEL
        print(f"\n使用预训练模型：{model_path}")

    # 加载模型
    model = YOLO(model_path)

    print(f"\n训练参数：")
    print(f"  epochs     = {EPOCHS}")
    print(f"  imgsz      = {IMG_SIZE}")
    print(f"  batch      = {BATCH_SIZE}")
    print(f"  patience   = {PATIENCE}（早停）")
    print(f"  device     = cpu（你的机器无独显）")
    print(f"\n输出目录：{PROJECT_DIR}/{RUN_NAME}")
    print("\n开始训练，请耐心等待（i5 CPU 预计 30~60 分钟）...\n")

    # 开始训练
    results = model.train(
        data=DATASET_DIR,
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        patience=PATIENCE,
        device="cpu",
        project=PROJECT_DIR,
        name=RUN_NAME,
        exist_ok=True,
        # 数据增强（小数据集必备）
        hsv_h=0.015,    # 色调抖动
        hsv_s=0.7,      # 饱和度抖动
        hsv_v=0.4,      # 明度抖动
        fliplr=0.5,     # 左右翻转
        degrees=15.0,   # 随机旋转 ±15度
        scale=0.3,      # 随机缩放
        translate=0.1,  # 随机平移
        erasing=0.3,    # 随机遮挡（防过拟合）
        # 训练过程显示
        verbose=True,
        plots=True,     # 保存训练曲线图
    )

    # 训练完成
    print("\n" + "=" * 60)
    print("训练完成！")
    best_model = Path(PROJECT_DIR) / RUN_NAME / "weights" / "best.pt"
    print(f"最佳模型路径：{best_model}")

    # 验证集评估
    print("\n在验证集上评估...")
    metrics = model.val()
    print(f"Top-1 准确率：{metrics.top1:.1%}")
    print(f"Top-5 准确率：{metrics.top5:.1%}")

    return str(best_model)


if __name__ == "__main__":
    best_model_path = train()
    print(f"\n下一步：将以下路径填入 config.py 的 LOCAL_MODEL_PATH：")
    print(f"  {best_model_path}")
