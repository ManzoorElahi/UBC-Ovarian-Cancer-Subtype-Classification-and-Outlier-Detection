# UBC-Ovarian-Cancer-Subtype-Classification-and-Outlier-Detection
UBC-OCEAN 4th place solution

## Environment
Use [TPU Kaggle Docker](https://gcr.io/kaggle-gpu-images/python-tpuvm@sha256:ac32fbff8fdb4b3208a99ed054416c5c31500e0ba60838044cc368869b9524a8).

## TFRecords
Datageneration can be skipped by using the below tfrecords.

- Add all the below tfrecords in `/data/wsimasks`
  
  [0](https://www.kaggle.com/datasets/mmelahi/ubc-ocean-wsi-masks-tfrecords-512-0-0)
  [1](https://www.kaggle.com/datasets/mmelahi/ubc-ocean-wsi-masks-tfrecords-512-1-0)
  [2](https://www.kaggle.com/datasets/mmelahi/ubc-ocean-wsi-masks-tfrecords-512-2-0)
  [3](https://www.kaggle.com/datasets/mmelahi/ubc-ocean-wsi-masks-tfrecords-512-2-1)
  [4](https://www.kaggle.com/datasets/mmelahi/ubc-ocean-wsi-masks-tfrecords-512-3-0)
  [5](https://www.kaggle.com/datasets/mmelahi/ubc-ocean-wsi-masks-tfrecords-512-4-0)

- Add [tfrecords](https://www.kaggle.com/datasets/mmelahi/ubc-ocean-thumbnails-masks-tfrecords-512) in `/data/thumbnailmaskssmall`
- Add [tfrecords](https://www.kaggle.com/code/mmelahi/ubc-ocean-thumbnails-masks-tfrecords-1) in `/data/thumbnailmasks`
- Add [tfrecords](https://www.kaggle.com/datasets/mmelahi/ubc-ocean-tfrecords-768-2) in `/data/croppedtfrecords`
  

## Usage
0. All trained model weights should be placed in `weights` folder. The main competition data, supplemental mask data, thumbnail tfrecords, thumbnail small tfrecords, wsi tfrecords, and cropped tfrecords should be placed in `/data/ubcocean`, `/data/supplementalmasks`, `/data/thumbnailmasks`, /data/thumbnailmaskssmall`, `/data/wsimasks`, and `/data/croppedtfrecords` respectively.
   
2. Generate TFRecords from thumbnail images & supplimental mask data
```bash
$ python thumbnailmasks.py
$ python thumbnailmaskssmall.py
```
2. Generate TFRecords from WSI & supplimental mask data
```bash
$ python wsimasks.py
```
3. Train segmentation models.
```bash
$ python convnextbasefpn25epochs.py
$ python convnextbasefpn.py
$ python convnextsmallfpn.py
$ python hornetbasefpn.py
$ python hornetsmallfpn.py
$ python model8.py
$ python model9.py
$ python model10.py
$ python model11.py
$ python model12.py
$ python model13.py
$ python model14.py
$ python model15.py
```

4. Use the segmentation model to generate cropped images
```bash
$ python gencroppeddata.py
$ python noncancerousdata.py
$ python croppedtfrecords.py
```
5. Train classification models
```bash
$ python model0.py
$ python model1.py
$ python model2.py
$ python model3.py
$ python model4.py
$ python model5.py
$ python model6.py
$ python model7.py
```
6. Inference
```bash
$ python inference.py
```
Kaggle inference notebook can be found [here](https://www.kaggle.com/code/mmelahi/ubc-ocean-final-inference).

## License
Apache-2.0
