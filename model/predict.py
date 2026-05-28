import argparse
from pathlib import Path
from typing import Optional, List, Union
from PIL import Image

from ultralytics import YOLO
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_PATH = REPO_ROOT / "weights" / "best.pt"


class Predictor:
    def __init__(self, model_path: Optional[Path] = None):
        if model_path is None:
            model_path = DEFAULT_MODEL_PATH
            print(f"using model {model_path} ")
        self.model = YOLO(str(model_path))

    def predict_image(self, image_source: Union[Path, str, Image.Image]) -> List[str]:
        if isinstance(image_source, (Path, str)):
            image_path = Path(image_source)
            if not image_path.is_file():
                raise FileNotFoundError(f"Image file {image_path} does not exist.")
            image = Image.open(str(image_path))
        else:
            image = image_source

        # predict and get results.
        results = self.model(image, conf=0.3, imgsz=1024, agnostic_nms=True)[0]

        detected_labels = []
        if results.boxes is not None and len(results.boxes) > 0:
            boxes = results.boxes.xywh.cpu().numpy()
            classes = results.boxes.cls.cpu().numpy()
            names = self.model.names

            # Sort tiles left-to-right by bounding box x-coordinate
            sorted_indices = np.argsort(boxes[:, 0])
            for idx in sorted_indices:
                label = names[int(classes[idx])]
                detected_labels.append(label)

        return detected_labels


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="predict image using YOLO model.")
    parser.add_argument(
        "-i", "--in_path", type=str, required=True, help="path of the image to predict."
    )
    parser.add_argument(
        "-m", "--model", type=str, help="path of the model. Use the default model if not provided."
    )
    args = parser.parse_args()

    predictor = Predictor(model_path=args.model)
    result_labels = predictor.predict_image(Path(args.in_path))
    print(f"Detected tiles: {result_labels}")
