#!/usr/bin/env python3
"""Compare models on the held-out test split (seed 1, never trained on).

    python finetune/evaluate.py yolov8m.pt finetune/runs/yolov8m_sim/weights/best.pt
"""

import argparse
import os

from ultralytics import YOLO

HERE = os.path.dirname(os.path.abspath(__file__))
CLASSES = [0, 2, 3, 5, 7]  # person, car, motorcycle, bus, truck


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('models', nargs='+')
    ap.add_argument('--imgsz', type=int, default=640)
    args = ap.parse_args()

    rows = []
    for path in args.models:
        m = YOLO(path).val(data=os.path.join(HERE, 'sim_traffic.yaml'), split='test',
                           imgsz=args.imgsz, batch=8, device=0, classes=CLASSES,
                           plots=False, verbose=False)
        names = m.names
        per_cls = {names[c]: (m.box.class_result(i)) for i, c in enumerate(m.box.ap_class_index)}
        rows.append((path, m.box.map50, m.box.map, per_cls))

    for path, map50, map5095, per_cls in rows:
        print(f'\n== {path}  mAP50={map50:.3f}  mAP50-95={map5095:.3f}')
        print(f'   {"class":<11}{"precision":>10}{"recall":>8}{"mAP50":>8}{"mAP50-95":>10}')
        for name, (p, r, ap50, ap) in per_cls.items():
            print(f'   {name:<11}{p:>10.3f}{r:>8.3f}{ap50:>8.3f}{ap:>10.3f}')


if __name__ == '__main__':
    main()
