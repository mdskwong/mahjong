import argparse
from pathlib import Path
import shutil
from ultralytics import YOLO

from utils import download_data, get_latest_model_path
# Un-comment the line below if you plan to use the dataset converter
# from convert_dataset import DatasetConverter

def parse_args():
    parser = argparse.ArgumentParser(description="Train a YOLOv11 Mahjong Detection Model.")
    parser.add_argument(
        "--version", 
        type=int, 
        default=18, 
        help="Roboflow dataset version to download and train on."
    )
    parser.add_argument(
        "--epochs", 
        type=int, 
        default=20, 
        help="Number of training epochs."
    )
    parser.add_argument(
        "--model", 
        type=str, 
        default="yolo11s.pt", 
        help="Initial YOLO model weights to load."
    )
    parser.add_argument(
        "--imgsz", 
        type=int, 
        default=1024, 
        help="Image size for training."
    )
    return parser.parse_args()

def main():
    args = parse_args()
    
    # 1. Download data from Roboflow
    data_root_path = Path(f"Mahjong_detect-{args.version}")
    if not data_root_path.exists():
        print(f"Downloading dataset version {args.version} from Roboflow...")
        download_data(args.version)
    else:
        print(f"Dataset path {data_root_path} already exists. Skipping download.")

    # 2. [Optional] Download and convert data from jaheel/MJOD-2136
    # Uncomment and adjust the paths below if you want to use the dataset converter script:
    """
    coco_mahjong_root_path = Path("/path/to/MJOD-2136")
    if coco_mahjong_root_path.exists():
        print("Converting supplementary COCO dataset...")
        dataset_converter = DatasetConverter(data_root_path, coco_mahjong_root_path)
        dataset_converter.convert()
    else:
        print(f"Supplementary dataset path {coco_mahjong_root_path} not found. Skipping conversion.")
    """

    # 3. Initialize and train the YOLO model
    print(f"Initializing model with {args.model}...")
    model = YOLO(args.model)
    
    print(f"Starting training for {args.epochs} epochs...")
    results = model.train(
        data=data_root_path.absolute() / "data.yaml",
        epochs=args.epochs,
        batch=-1,       # use ~60% of GPU memory
        device=0,       # use GPU device 0
        imgsz=args.imgsz
    )
    
    # 4. Save the trained model to the weights folder
    weights_dir = Path("weights")
    weights_dir.mkdir(exist_ok=True)
    best_model = get_latest_model_path(Path("runs/detect")).with_name("best.pt")
    if best_model.exists():
        shutil.copy(best_model, weights_dir / "best.pt")
        print(f"Model saved to {weights_dir.absolute() / 'best.pt'}")
    
    print("Training complete!")

if __name__ == "__main__":
    main()