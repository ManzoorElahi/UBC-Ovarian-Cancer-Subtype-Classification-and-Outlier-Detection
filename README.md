# UBC-Ovarian-Cancer-Subtype-Classification-and-Outlier-Detection
UBC-OCEAN 4th place solution

1. Generate TFRecords from thumbnail images & supplimental mask data
```bash
$ python thumbnailmasks.py
```
2. Generate TFRecords from WSI & supplimental mask data
```bash
$ python wsimasks.py
```
3. Train segmentation models.
```bash
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
