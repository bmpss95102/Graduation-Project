import argparse
import settings

parser = argparse.ArgumentParser(
    description="偵測與繪製 Mask R-CNN 來偵測辨識腹腔器官",
    add_help=True,
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)

parser.add_argument(
    '--name',
    required=True,
    default="Peritoneal",
    metavar="'Recognizable Name'",
    help="可辨識名稱"
)

parser.add_argument(
    '--images',
    required=True,
    metavar="/docs/to/your/dataset/",
    help="圖片集的路徑"
)

parser.add_argument(
    '--weights',
    required=True,
    metavar="/docs/to/weights.h5/",
    help="權重檔案(.h5)的路徑"
)

parser.add_argument(
    '--logs',
    required=False,
    default=settings.DEFAULT_LOGS_DIR,
    metavar="輸出日誌的路徑"
)

args = parser.parse_args()
