{"metadata":{"kaggle":{"accelerator":"tpu1vmV38","dataSources":[{"sourceId":7318758,"sourceType":"datasetVersion","datasetId":4230522},{"sourceId":7324870,"sourceType":"datasetVersion","datasetId":4250844}],"isInternetEnabled":true,"language":"python","sourceType":"script","isGpuEnabled":false},"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"codemirror_mode":{"name":"ipython","version":3},"file_extension":".py","mimetype":"text/x-python","name":"python","nbconvert_exporter":"python","pygments_lexer":"ipython3","version":"3.10.13"},"papermill":{"default_parameters":{},"duration":1959.223278,"end_time":"2024-01-03T05:08:28.693962","environment_variables":{},"exception":null,"input_path":"__notebook__.ipynb","output_path":"__notebook__.ipynb","parameters":{},"start_time":"2024-01-03T04:35:49.470684","version":"2.5.0"}},"nbformat_minor":4,"nbformat":4,"cells":[{"cell_type":"code","source":"!pip install keras-cv-attention-models==1.3.22\n\nimport numpy as np\nimport pandas as pd\nimport os, random, math, gc\nimport matplotlib.pyplot as plt\nfrom sklearn.model_selection import GroupKFold, StratifiedKFold, KFold\nimport tensorflow as tf\nfrom tqdm import tqdm\nfrom keras_cv_attention_models import convnext, efficientnet, hornet, beit, davit\n\nSEED=9045\nrandom.seed(SEED)\nos.environ['PYTHONHASHSEED'] = str(SEED)\nnp.random.seed(SEED)\ntf.random.set_seed(SEED)\n\ntfrecords_path = '/data/croppedtfrecords'\n\nALL_FILENAMES = np.sort(np.array(tf.io.gfile.glob(tfrecords_path + '/*.tfrec')))\n\nimport re\ndef count_data_items(filenames):\n    n = [int(re.compile(r\"-([0-9]*)\\.\").search(filename).group(1)) for filename in filenames]\n    return np.sum(n)\n\npolicy = tf.keras.mixed_precision.Policy('float32')\ntf.keras.mixed_precision.set_global_policy(policy)\n\nprint(f'Compute dtype: {tf.keras.mixed_precision.global_policy().compute_dtype}')\nprint(f'Variable dtype: {tf.keras.mixed_precision.global_policy().variable_dtype}')\n\nAUTO = tf.data.experimental.AUTOTUNE\n\ntry:\n    cluster_resolver = tf.distribute.cluster_resolver.TPUClusterResolver(tpu=\"local\")\n    tf.config.experimental_connect_to_cluster(cluster_resolver)\n    tf.tpu.experimental.initialize_tpu_system(cluster_resolver)\n    strategy = tf.distribute.TPUStrategy(cluster_resolver)\n    print(\"on TPU\")\nexcept tf.errors.NotFoundError:\n    print(\"not on TPU\")\n    strategy = tf.distribute.MirroredStrategy()\n    \nprint(\"REPLICAS: \", strategy.num_replicas_in_sync)\n    \nBATCH_SIZE = 16*strategy.num_replicas_in_sync\n\n# # Datagenerator\n\nAUG_IMG = np.ones((8,768,768,3),dtype=np.float32)\n\nfor i,j in zip([150,450], [16,64]):\n    AUG_IMG[0,i:i+j,:,:] = 0\n    AUG_IMG[0,:,i:i+j,:] = 0\n    \nfor i,j in zip([150,450], [64,16]):\n    AUG_IMG[1,i-j:i,:,:] = 0\n    AUG_IMG[1,:,i-j:i,:] = 0\n    \nAUG_IMG[2,80:260,480:660,:] = 0\nAUG_IMG[2,480:660,80:260,:] = 0\n\nAUG_IMG[3,80:260,80:260,:] = 0\nAUG_IMG[3,480:660,480:660,:] = 0\n\nAUG_IMG = tf.cast(AUG_IMG,tf.float32)\n\nMEAN = tf.cast([0.485, 0.456, 0.406], tf.float32)\nMEAN = tf.reshape(MEAN, [1, 1, 3])\nSTD = tf.cast([0.229, 0.224, 0.225], tf.float32)\nSTD = tf.reshape(STD, [1, 1, 3])\nAUG = tf.cast([[1.0,0.0],\n               [0.0,1.0]], tf.float32)\n\ndef read_tfrecord(example):\n    feature_description = {\n        'img': tf.io.FixedLenFeature([], tf.string),\n        'y': tf.io.FixedLenFeature([], tf.string),\n    }\n    example = tf.io.parse_single_example(example, feature_description)\n    img = tf.io.decode_raw(example['img'], tf.uint8)\n    img = tf.reshape(img, [768, 768, 3])\n    img = tf.cast(img, tf.float32)/255.0\n    \n    y = tf.io.decode_raw(example['y'], tf.uint8)\n    y = tf.reshape(y, [5])\n    y = tf.cast(y, tf.float32)\n\n    return img, y\n\n\ndef read_tfrecords_train(example):\n    img, y = read_tfrecord(example)\n    \n    img0 = tf.image.flip_up_down(img)\n    ids = tf.random.shuffle(AUG)[0,:]\n    img = ids[0]*img0 + ids[1]*img\n    \n    img0 = tf.image.flip_left_right(img)\n    ids = tf.random.shuffle(AUG)[0,:]\n    img = ids[0]*img0 + ids[1]*img\n    \n    img0 = tf.image.rot90(img, k=1)    \n    ids = tf.random.shuffle(AUG)[0,:]\n    img = ids[0]*img0 + ids[1]*img\n    \n    img0 = tf.image.rot90(img, k=-1)    \n    ids = tf.random.shuffle(AUG)[0,:]\n    img = ids[0]*img0 + ids[1]*img\n    \n    img0 = tf.image.rot90(img, k=3)    \n    ids = tf.random.shuffle(AUG)[0,:]\n    img = ids[0]*img0 + ids[1]*img\n    \n    img0 = tf.image.rot90(img, k=-3)    \n    ids = tf.random.shuffle(AUG)[0,:]\n    img = ids[0]*img0 + ids[1]*img\n    \n    idx = tf.random.uniform(shape=[], maxval=8, dtype=tf.int32)\n    img = AUG_IMG[idx]*img\n    \n    img = img - MEAN\n    img = img / STD\n    \n    img = tf.image.random_hue(img, 0.2)\n    img = tf.image.random_saturation(img, 0.9, 1.2)\n    img = tf.image.random_contrast(img, 0.85, 1.25)\n    igm = tf.image.random_brightness(img, 0.1)    \n    \n    return img, y\n\n\ndef read_tfrecords_valid(example):\n    img, y = read_tfrecord(example)   \n    img = img - MEAN\n    img = img / STD\n    return img, y\n\n\ndef load_dataset_train(filenames, batch_size=32, repeat=True, shuffle=True, ordered=False):\n    ignore_order = tf.data.Options()\n    if not ordered:\n        ignore_order.experimental_deterministic = False # disable order, increase speed\n\n    files = tf.data.Dataset.from_tensor_slices(filenames)\n    dataset = tf.data.TFRecordDataset(files, compression_type=\"GZIP\", num_parallel_reads=AUTO)\n    dataset = dataset.with_options(ignore_order) # uses data as soon as it streams in, rather than in its original order\n    if repeat:\n        dataset = dataset.map(read_tfrecords_train, num_parallel_calls=AUTO)\n        dataset = dataset.repeat()\n    else:\n        dataset = dataset.map(read_tfrecords_valid, num_parallel_calls=AUTO)\n    if shuffle:\n        dataset = dataset.shuffle(buffer_size=6024)\n    dataset = dataset.batch(batch_size)\n    dataset = dataset.prefetch(AUTO)\n    \n    return dataset\n\n# # Model\n\ndef get_model():\n    \n    base_layer = efficientnet.EfficientNetV2B2(input_shape=(768,768,3), pretrained='imagenet', \n                                               drop_connect_rate=0.1, num_classes=0)\n    \n    inputs = base_layer.input\n\n    y = base_layer.get_layer('post_swish').output\n    \n    y = tf.keras.layers.GlobalAveragePooling2D(name='global_ave')(y)\n    y = tf.keras.layers.Dropout(0.2, name='dropout')(y)\n    y = tf.keras.layers.Dense(5, dtype=\"float32\", activation='sigmoid', \n                              name='class_output')(y)\n    \n    model = tf.keras.Model(inputs=inputs, outputs=y)\n    return model\n\n# # LR Schedule\n\nimport math\nimport matplotlib.pyplot as plt\n\nLR_START = 1e-6\nLR_MAX = 1e-3\nLR_MIN = 5e-6\nLR_RAMPUP_EPOCHS = 4\nLR_SUSTAIN_EPOCHS = 0\nEPOCHS = 25\n\ndef lrfn(epoch):\n    if epoch < LR_RAMPUP_EPOCHS:\n        lr = (LR_MAX - LR_START) / LR_RAMPUP_EPOCHS * epoch + LR_START\n    elif epoch < LR_RAMPUP_EPOCHS + LR_SUSTAIN_EPOCHS:\n        lr = LR_MAX\n    else:\n        decay_total_epochs = EPOCHS - LR_RAMPUP_EPOCHS - LR_SUSTAIN_EPOCHS - 1\n        decay_epoch_index = epoch - LR_RAMPUP_EPOCHS - LR_SUSTAIN_EPOCHS\n        phase = math.pi * decay_epoch_index / decay_total_epochs\n        cosine_decay = 0.5 * (1 + math.cos(phase))\n        lr = (LR_MAX - LR_MIN) * cosine_decay + LR_MIN\n    return lr\n\nrng = [i for i in range(EPOCHS)]\nlr_y = [lrfn(x) for x in rng]\nplt.figure(figsize=(10, 4))\nplt.plot(rng, lr_y)\nprint(\"Learning rate schedule: {:.3g} to {:.3g} to {:.3g}\". \\\n      format(lr_y[0], max(lr_y), lr_y[-1]))\n\n# # Training\n\ntf.keras.backend.clear_session()\n    \nTRAINING_STEPS = 6024//BATCH_SIZE\ntrain_ds = load_dataset_train(ALL_FILENAMES, batch_size=BATCH_SIZE, repeat=True, shuffle=True)\n\nwith strategy.scope():\n    \n    model = get_model()\n\n    opt = tf.keras.optimizers.AdamW(learning_rate=1e-5, weight_decay=1e-2)#, clipnorm=1.0)\n    opt.exclude_from_weight_decay(var_names=[\"layernorm\", \"layer_normalization\", \"LayerNorm\", \n                                             \"layer_norm\", \"ln\", \"bn\", \"bias\"])\n\n    model.compile(loss=tf.keras.losses.BinaryCrossentropy(),\n                  optimizer=opt,\n                  metrics=None)\n\nlr_callback = tf.keras.callbacks.LearningRateScheduler(lrfn, verbose=True)\n        \n_ = model.fit(train_ds,\n              steps_per_epoch=TRAINING_STEPS,\n              callbacks=[lr_callback],\n              epochs=EPOCHS)\n\nmodel.save_weights(f'model_efficientnetv2b2_2.h5')","metadata":{"_uuid":"65353e8d-b9b2-4e03-ab1d-4283955f1a85","_cell_guid":"367151fb-bcb8-41e2-a16b-29533de8972e","collapsed":false,"jupyter":{"outputs_hidden":false},"trusted":true},"execution_count":null,"outputs":[]}]}