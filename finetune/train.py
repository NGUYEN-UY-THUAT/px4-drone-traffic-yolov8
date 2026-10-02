#!/usr/bin/env python3
"""Fine-tune yolov8m.pt on the auto-labelled Gazebo traffic dataset.

    python finetune/train.py --epochs 30 --imgsz 640 --batch 4

The best weights end up in finetune/runs/<name>/weights/best.pt.
"""

import argparse
import os

from ultralytics import YOLO

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default=os.path.join(HERE, '..', 'yolov8m.pt'))
    ap.add_argument('--epochs', type=int, default=30)
    ap.add_argument('--imgsz', type=int, default=640)
    ap.add_argument('--batch', type=int, default=4)
    ap.add_argument('--name', default='yolov8m_sim')
    ap.add_argument('--resume', action='store_true',
                    help='continue an interrupted run from runs/<name>/weights/last.pt')
    args = ap.parse_args()

    if args.resume:
        last = os.path.join(HERE, 'runs', args.name, 'weights', 'last.pt')
        YOLO(last).train(resume=True, batch=args.batch, device=0)
        return

    model = YOLO(args.model)
    model.train(
        data=os.path.join(HERE, 'sim_traffic.yaml'),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=0,
        workers=6,
        project=os.path.join(HERE, 'runs'),
        name=args.name,
        exist_ok=True,
        patience=10,
        # Small dataset on top of a strong COCO model: gentle LR, short warmup
        lr0=0.002,
        warmup_epochs=1,
        # Drone views: any heading, so flip both ways; no colour-shift heavy aug
        fliplr=0.5,
        flipud=0.5,
        degrees=10,
        scale=0.5,
        mosaic=1.0,
        close_mosaic=5,
        plots=True,
    )


if __name__ == '__main__':
    main()
