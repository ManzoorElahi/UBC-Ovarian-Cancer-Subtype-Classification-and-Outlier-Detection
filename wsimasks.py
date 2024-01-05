{"metadata":{"kernelspec":{"language":"python","display_name":"Python 3","name":"python3"},"language_info":{"name":"python","version":"3.10.12","mimetype":"text/x-python","codemirror_mode":{"name":"ipython","version":3},"pygments_lexer":"ipython3","nbconvert_exporter":"python","file_extension":".py"},"kaggle":{"accelerator":"none","dataSources":[{"sourceId":45867,"databundleVersionId":6924515,"sourceType":"competition"},{"sourceId":6774400,"sourceType":"datasetVersion","datasetId":3895136},{"sourceId":6984590,"sourceType":"datasetVersion","datasetId":4014175}],"isInternetEnabled":true,"language":"python","sourceType":"script","isGpuEnabled":false}},"nbformat_minor":4,"nbformat":4,"cells":[{"cell_type":"code","source":"# https://www.kaggle.com/code/jirkaborovec/cancer-subtype-cut-wsi-tiles-mask-0-25x/notebook\n\n# intall the deb packages\n!dpkg -i /packages/pyvips-python-and-deb-package/linux_packages/archives/*.deb\n# install the python wrapper\n!pip install pyvips -f /packages/pyvips-python-and-deb-package/python_packages/ --no-index\n\nimport pyvips\nimport numpy as np\nimport pandas as pd\nimport os, random, math, gc, cv2\nimport matplotlib.pyplot as plt\nfrom sklearn.model_selection import GroupKFold, StratifiedKFold, KFold\nimport tensorflow as tf\nfrom tqdm import tqdm\nfrom PIL import Image\n\nos.environ['VIPS_DISC_THRESHOLD'] = '9gb'\n\nSEED=8677\nrandom.seed(SEED)\nos.environ['PYTHONHASHSEED'] = str(SEED)\nnp.random.seed(SEED)\ntf.random.set_seed(SEED)\n\ndf_train = pd.read_csv('/data/ubcocean/train.csv')\ndf_train.head()\n\ndf_train['label'].value_counts()\n\ndf_train['is_tma'].value_counts()\n\nlabel_map = {x:y for x,y in zip(df_train['image_id'].values,df_train['label'].values)}\nsubtype_map = {'CC':0, 'EC':1, 'HGSC':2, 'LGSC':3, 'MC':4}\nfile_names = [int(f.split('.')[0]) for f in os.listdir('/data/supplementalmasks')]\nlabels = [label_map[x] for x in file_names]\ndf_mask = pd.DataFrame({'image_id':file_names, 'label':labels})\ndf_mask['y'] = df_mask['label'].map(subtype_map)\ndf_mask.head()\n\ndf_mask['label'].value_counts()\n\ndf_mask['y'].value_counts()\n\nTILE_SIZE = 512\n\ndef _bytes_feature(value):\n    \"\"\"Returns a bytes_list from a string / byte.\"\"\"\n    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))\n\ndef serialize_example(img, msk, y):\n    feature = {\n        'img': _bytes_feature(img),\n        'msk': _bytes_feature(msk),\n        'y': _bytes_feature(y),\n    }\n    example_proto = tf.train.Example(features=tf.train.Features(feature=feature))\n    return example_proto.SerializeToString()\n\n!mkdir /data/wsimasks\n\ncount = 0\nopts = tf.io.TFRecordOptions(compression_type=\"GZIP\")\nkf = KFold(n_splits=df_mask.shape[0], random_state=42, shuffle=True)\n\nfor fold, (train_index, test_index) in enumerate(kf.split(df_mask)):\n    if fold < 60:\n        image_ids = df_mask['image_id'].values[test_index]\n        y_test = df_mask['y'].values[test_index]\n        tfr_filename = f'/data/wsimasks/ubc-ocean-2023-msk-{fold:03}.tfrec'\n        with tf.io.TFRecordWriter(tfr_filename, options=opts) as writer:\n            for img_id,y in zip(image_ids,y_test):\n                \n                img_path = f'/data/ubcocean/train_images/{img_id}.png'\n                img = pyvips.Image.new_from_file(img_path).numpy()[:,:,:3]\n                h,w = img.shape[0], img.shape[1]\n                img = cv2.resize(img, (w//2, h//2), interpolation = cv2.INTER_CUBIC)\n                \n                msk_path = f'/data/supplementalmasks/{img_id}.png'\n                msk = pyvips.Image.new_from_file(msk_path).numpy()[:,:,:3]\n                msk = cv2.resize(msk, (w//2, h//2), interpolation = cv2.INTER_CUBIC)\n                \n\n                for mag in [1, 1/np.sqrt(2.0), 1/np.sqrt(2.0)]:\n                \n                    h,w = img.shape[0], img.shape[1]\n                    h,w = int(h*mag), int(w*mag)\n                    if mag < 1:\n                        img = cv2.resize(img, (w, h), interpolation = cv2.INTER_CUBIC)\n                        msk = cv2.resize(msk, (w, h), interpolation = cv2.INTER_CUBIC)\n\n                    for i in range(0,img.shape[0]-TILE_SIZE,TILE_SIZE):\n                        for j in range(0,img.shape[1]-TILE_SIZE,TILE_SIZE):\n                            \n                            yoh = np.zeros(5,dtype=np.uint8)\n\n                            if np.clip(msk[i:i+TILE_SIZE, j:j+TILE_SIZE,:],0,1).sum() > 0.20*TILE_SIZE*TILE_SIZE:\n                                \n                                if np.clip(msk[i:i+TILE_SIZE, j:j+TILE_SIZE,0],0,1).sum() > 500:\n                                    yoh[y] = 1\n\n                                example = serialize_example(img[i:i+TILE_SIZE, j:j+TILE_SIZE,:].tobytes(), \n                                                            cv2.resize(msk[i:i+TILE_SIZE, j:j+TILE_SIZE,:], \n                                                                       (TILE_SIZE//2, TILE_SIZE//2), \n                                                                       interpolation = cv2.INTER_CUBIC).tobytes(), \n                                                            yoh.tobytes())\n                                writer.write(example)\n\n                                count += 1\n                                \n                del img, msk\n                gc.collect()\n\ny, count\n\nyoh","metadata":{"_uuid":"c2ad73a8-e650-4a78-95aa-71083f361fd9","_cell_guid":"8080c713-dfbb-4200-81a5-714aa0406838","collapsed":false,"jupyter":{"outputs_hidden":false},"trusted":true},"execution_count":null,"outputs":[]}]}