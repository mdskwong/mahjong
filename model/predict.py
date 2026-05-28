import argparse
from pathlib import Path
from typing import Optional
from PIL import Image

from ultralytics import YOLO
import supervision as sv
import numpy as np
from utils import get_latest_model_path, LABEL_MAPPING


class Predictor:
    def __init__(
        self, model_path: Optional[Path] = None, *, font_path: str, font_size: int = 24
    ):
        if model_path is None:
            model_path = Path("weights/best.pt")
            if not model_path.exists():
                # Fallback to the latest model in runs/detect
                model_path = get_latest_model_path(Path("runs/detect"))
            print(f"using model {model_path} ")
        self.model = YOLO(str(model_path))

        self.font_path = font_path
        self.font_size = font_size  # Set the desired font size

        self.box_annotator: sv.BoxAnnotator = sv.BoxAnnotator()
        self.label_annotator: sv.RichLabelAnnotator = sv.RichLabelAnnotator(
            font_path=self.font_path,
            font_size=self.font_size,
            smart_position=True,
        )

    def draw_results_on_image(
        self, image: Image.Image, detections: sv.Detections
    ) -> Image.Image:
        # Filter detections with confidence > 0.5
        detections = detections[detections.confidence > 0.5]
        labels = [
            f"{LABEL_MAPPING[self.model.model.names[class_id]]} {confidence:.2f}"
            for class_id, confidence in zip(detections.class_id, detections.confidence)
        ]
        annotated_image = self.box_annotator.annotate(
            scene=image, detections=detections
        )
        annotated_image = self.label_annotator.annotate(
            scene=annotated_image, detections=detections, labels=labels
        )

        return annotated_image

    def predict_image(self, image_path: Path, find_winning_hand: bool) -> Image.Image:
        if not image_path.is_file():
            raise FileNotFoundError(f"Image file {image_path} does not exist.")
        image = Image.open(str(image_path))

        # predict and draw results on the image.
        results = self.model(image, conf=0.3, imgsz=1024, agnostic_nms=True)[0]

        result_image = self.draw_results_on_image(
            image, sv.Detections.from_ultralytics(results)
        )
        return result_image


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="predict image using YOLO model.")
    parser.add_argument(
        "-i",
        "--in_path",
        type=str,
        help="path of the image to predict.",
    )
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        help="path of the model. Use the latest model if not provided.",
    )
    parser.add_argument(
        "--font_size",
        type=int,
        default=12,
        help="font size of label.",
    )
    parser.add_argument(
        "--font_path",
        type=str,
        default="/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",  # Path to a chinese font
        help="font path for label text.",
    )
    parser.add_argument("--find_winning_hand", action=argparse.BooleanOptionalAction)
    args = parser.parse_args()

    # predict and draw results on the image.
    predictor = Predictor(
        model_path=args.model, font_size=args.font_size, font_path=args.font_path
    )
    result_img = predictor.predict_image(Path(args.in_path), args.find_winning_hand)
    sv.plot_image(result_img)
