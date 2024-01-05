{"metadata":{"kaggle":{"accelerator":"tpu1vmV38","dataSources":[{"sourceId":7233969,"sourceType":"datasetVersion","datasetId":4166908},{"sourceId":7233973,"sourceType":"datasetVersion","datasetId":4166915},{"sourceId":7233976,"sourceType":"datasetVersion","datasetId":4166918},{"sourceId":7233977,"sourceType":"datasetVersion","datasetId":4166920},{"sourceId":7233981,"sourceType":"datasetVersion","datasetId":4166923},{"sourceId":7233982,"sourceType":"datasetVersion","datasetId":4166925}],"isInternetEnabled":true,"language":"python","sourceType":"script","isGpuEnabled":false},"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},"language_info":{"codemirror_mode":{"name":"ipython","version":3},"file_extension":".py","mimetype":"text/x-python","name":"python","nbconvert_exporter":"python","pygments_lexer":"ipython3","version":"3.10.13"},"papermill":{"default_parameters":{},"duration":19418.76455,"end_time":"2023-12-23T08:06:11.093996","environment_variables":{},"exception":null,"input_path":"__notebook__.ipynb","output_path":"__notebook__.ipynb","parameters":{},"start_time":"2023-12-23T02:42:32.329446","version":"2.5.0"}},"nbformat_minor":4,"nbformat":4,"cells":[{"cell_type":"code","source":"!pip install keras-cv-attention-models==1.3.22\n\nimport numpy as np\nimport pandas as pd\nimport os, random, math, gc\nimport matplotlib.pyplot as plt\nfrom sklearn.model_selection import GroupKFold, StratifiedKFold, KFold\nimport tensorflow as tf\nfrom tqdm import tqdm\nfrom keras_cv_attention_models import convnext, efficientnet, hornet, beit, davit\n\nSEED=2721\nrandom.seed(SEED)\nos.environ['PYTHONHASHSEED'] = str(SEED)\nnp.random.seed(SEED)\ntf.random.set_seed(SEED)\n\ntfrecords_path = '/data/wsimasks'\nALL_FILENAMES = np.sort(np.array(tf.io.gfile.glob(tfrecords_path + '/*.tfrec')))\n\nimport re\ndef count_data_items(filenames):\n    n = [int(re.compile(r\"-([0-9]*)\\.\").search(filename).group(1)) for filename in filenames]\n    return np.sum(n)\n\npolicy = tf.keras.mixed_precision.Policy('float32')\ntf.keras.mixed_precision.set_global_policy(policy)\n\nprint(f'Compute dtype: {tf.keras.mixed_precision.global_policy().compute_dtype}')\nprint(f'Variable dtype: {tf.keras.mixed_precision.global_policy().variable_dtype}')\n\nAUTO = tf.data.experimental.AUTOTUNE\n\ntry:\n    cluster_resolver = tf.distribute.cluster_resolver.TPUClusterResolver(tpu=\"local\")\n    tf.config.experimental_connect_to_cluster(cluster_resolver)\n    tf.tpu.experimental.initialize_tpu_system(cluster_resolver)\n    strategy = tf.distribute.TPUStrategy(cluster_resolver)\n    print(\"on TPU\")\nexcept tf.errors.NotFoundError:\n    print(\"not on TPU\")\n    strategy = tf.distribute.MirroredStrategy()\n    \nprint(\"REPLICAS: \", strategy.num_replicas_in_sync)\n    \nBATCH_SIZE = 16*strategy.num_replicas_in_sync\n\n# # Datagenerator\n\nMEAN = tf.cast([0.485, 0.456, 0.406], tf.float32)\nMEAN = tf.reshape(MEAN, [1, 1, 3])\nSTD = tf.cast([0.229, 0.224, 0.225], tf.float32)\nSTD = tf.reshape(STD, [1, 1, 3])\nAUG = tf.cast([[1.0,0.0],\n               [0.0,1.0]], tf.float32)\n\ndef read_tfrecord(example):\n    feature_description = {\n        'img': tf.io.FixedLenFeature([], tf.string),\n        'msk': tf.io.FixedLenFeature([], tf.string),\n        'y': tf.io.FixedLenFeature([], tf.string),\n    }\n    example = tf.io.parse_single_example(example, feature_description)\n    img = tf.io.decode_raw(example['img'], tf.uint8)\n    img = tf.reshape(img, [512, 512, 3])\n    img = tf.cast(img, tf.float32)/255.0\n    img = img - MEAN\n    img = img / STD\n    \n    msk = tf.io.decode_raw(example['msk'], tf.uint8)\n    msk = tf.reshape(msk, [256, 256, 3])\n    msk = tf.cast(msk, tf.float32)\n    msk = tf.clip_by_value(msk,0.0,1.0)\n    \n    y = tf.io.decode_raw(example['y'], tf.uint8)\n    y = tf.reshape(y, [5])\n    y = tf.cast(y, tf.float32)\n\n    return img, msk, y\n\n\ndef read_tfrecords_train(example):\n    img, msk, y = read_tfrecord(example)\n    \n    img = tf.image.random_hue(img, 0.2)\n    img = tf.image.random_saturation(img, 0.8, 1.2)\n    img = tf.image.random_contrast(img, 0.5, 1.25)\n    igm = tf.image.random_brightness(img, 0.2)\n    \n    img0 = tf.image.flip_up_down(img)\n    msk0 = tf.image.flip_up_down(msk)\n    \n    ids = tf.random.shuffle(AUG)[0,:]\n    img = ids[0]*img0 + ids[1]*img\n    msk = ids[0]*msk0 + ids[1]*msk\n    \n    img0 = tf.image.flip_left_right(img)\n    msk0 = tf.image.flip_left_right(msk)\n    \n    ids = tf.random.shuffle(AUG)[0,:]\n    img = ids[0]*img0 + ids[1]*img\n    msk = ids[0]*msk0 + ids[1]*msk\n    \n    img0 = tf.image.rot90(img, k=1)\n    msk0 = tf.image.rot90(msk, k=1)\n    \n    ids = tf.random.shuffle(AUG)[0,:]\n    img = ids[0]*img0 + ids[1]*img\n    msk = ids[0]*msk0 + ids[1]*msk\n    \n    img0 = tf.image.rot90(img, k=-1)\n    msk0 = tf.image.rot90(msk, k=-1)\n    \n    ids = tf.random.shuffle(AUG)[0,:]\n    img = ids[0]*img0 + ids[1]*img\n    msk = ids[0]*msk0 + ids[1]*msk\n    \n    return img, {'mask_output':msk, 'class_output':y}\n\n\ndef read_tfrecords_valid(example):\n    img, msk, y = read_tfrecord(example)   \n    \n    return img, {'mask_output':msk, 'class_output':y}\n\n\ndef load_dataset_train(filenames, batch_size=32, repeat=True, shuffle=True, ordered=False):\n    ignore_order = tf.data.Options()\n    if not ordered:\n        ignore_order.experimental_deterministic = False # disable order, increase speed\n\n    files = tf.data.Dataset.from_tensor_slices(filenames)\n    dataset = tf.data.TFRecordDataset(files, compression_type=\"GZIP\", num_parallel_reads=AUTO)\n    dataset = dataset.with_options(ignore_order) # uses data as soon as it streams in, rather than in its original order\n    if repeat:\n        dataset = dataset.map(read_tfrecords_train, num_parallel_calls=AUTO)\n        dataset = dataset.repeat()\n    else:\n        dataset = dataset.map(read_tfrecords_valid, num_parallel_calls=AUTO)\n    if shuffle:\n        dataset = dataset.shuffle(buffer_size=25000)\n    dataset = dataset.batch(batch_size)\n    dataset = dataset.prefetch(AUTO)\n    \n    return dataset\n\n# # Model\n\ndef FPNBlock(inputs0, inputs1, output_channel, activation=\"gelu\", name=''):\n    nn0 = tf.keras.layers.Conv2D(output_channel, kernel_size=1, strides=1, padding=\"same\", name=name+'_conv2d_0')(inputs0)\n    nn1 = tf.keras.layers.Conv2D(output_channel, kernel_size=1, strides=1, padding=\"same\", name=name+'_conv2d_1')(inputs1)\n    nn1 = tf.keras.layers.UpSampling2D(2, name=name+'_up_0')(nn1)\n    nn = tf.keras.layers.Concatenate(name=name+'_merge_0')([nn0, nn1])\n    return nn\n\ndef UpBlockFinal(inputs, output_channel, activation=\"gelu\", name=''):\n    nn = tf.keras.layers.UpSampling2D(2, name=name+'_up_0')(inputs)\n    nn = tf.keras.layers.Conv2D(output_channel, kernel_size=3, strides=1, padding=\"same\", name=name+'_conv2d_0')(nn)\n    nn = tf.keras.layers.LayerNormalization(axis=-1, epsilon=1e-6, name=name+'_ln_0')(nn)\n    nn = tf.keras.layers.Activation(activation=activation, name=name+'_act_0')(nn)\n    nn = tf.keras.layers.Conv2D(output_channel, kernel_size=3, strides=1, padding=\"same\", name=name+'_conv2d_1')(nn)\n    nn = tf.keras.layers.LayerNormalization(axis=-1, epsilon=1e-6, name=name+'_ln_1')(nn)\n    nn = tf.keras.layers.Activation(activation=activation, name=name+'_act_1')(nn)\n    return nn\n\ndef ConvBlock(inputs, output_channel, activation=\"gelu\", name=''):\n    nn = tf.keras.layers.Conv2D(output_channel, kernel_size=3, strides=1, padding=\"same\", name=name+'_conv2d_0')(inputs)\n    nn = tf.keras.layers.LayerNormalization(axis=-1, epsilon=1e-6, name=name+'_ln_0')(nn)\n    nn = tf.keras.layers.Activation(activation=activation, name=name+'_act_0')(nn)\n    nn = tf.keras.layers.Conv2D(output_channel, kernel_size=3, strides=1, padding=\"same\", name=name+'_conv2d_1')(nn)\n    nn = tf.keras.layers.LayerNormalization(axis=-1, epsilon=1e-6, name=name+'_ln_1')(nn)\n    nn = tf.keras.layers.Activation(activation=activation, name=name+'_act_1')(nn)\n    return nn\n\ndef get_model_fpn():\n    \n    base_layer = efficientnet.EfficientNetV1B2(input_shape=(512,512,3), pretrained='imagenet', \n                                               drop_connect_rate=0.1, num_classes=0)\n    \n    inputs = base_layer.input\n\n    nn0 = base_layer.get_layer('stack_0_block1_output').output\n    nn1 = base_layer.get_layer('stack_1_block2_output').output\n    nn2 = base_layer.get_layer('stack_2_block2_output').output\n    nn3 = base_layer.get_layer('stack_4_block3_output').output\n    nn4 = base_layer.get_layer('stack_6_block1_output').output\n    \n    y = base_layer.get_layer('post_swish').output\n    y = tf.keras.layers.GlobalAveragePooling2D(name='global_ave')(y)\n    y = tf.keras.layers.Dropout(0.2, name='dropout')(y)\n    y = tf.keras.layers.Dense(5, dtype=\"float32\", activation='sigmoid', \n                              name='class_output')(y)\n        \n    nn3 = FPNBlock(nn3, nn4, 128, activation=\"gelu\", name='fpn3')\n    nn2 = FPNBlock(nn2, nn3, 128, activation=\"gelu\", name='fpn2')\n    nn1 = FPNBlock(nn1, nn2, 128, activation=\"gelu\", name='fpn1')\n    nn0 = FPNBlock(nn0, nn1, 128, activation=\"gelu\", name='fpn0')\n    \n    nn3 = ConvBlock(nn3, 128, activation=\"gelu\", name='convblock_3')\n    nn2 = ConvBlock(nn2, 128, activation=\"gelu\", name='convblock_2')\n    nn1 = ConvBlock(nn1, 128, activation=\"gelu\", name='convblock_1')\n    nn0 = ConvBlock(nn0, 128, activation=\"gelu\", name='convblock_0')\n    \n    nn3 = tf.keras.layers.UpSampling2D(8, name='fpn_up_3')(nn3)\n    nn2 = tf.keras.layers.UpSampling2D(4, name='fpn_up_2')(nn2)\n    nn1 = tf.keras.layers.UpSampling2D(2, name='fpn_up_1')(nn1)\n    \n    nn = tf.keras.layers.Add(name='fpn_merge_0')([nn0, nn1, nn2, nn3])\n    nn = ConvBlock(nn, 64, activation=\"gelu\", name='fpn_final')\n    \n    nn = tf.keras.layers.Conv2D(3, kernel_size=3, padding=\"same\", \n                                dtype=\"float32\", activation='sigmoid', \n                                name='mask_output')(nn)\n    \n    model = tf.keras.Model(inputs=inputs, outputs=[nn,y])\n    return model\n\n# # LR Schedule\n\nimport math\nimport matplotlib.pyplot as plt\n\nLR_START = 1e-6\nLR_MAX = 1e-3\nLR_MIN = 5e-6\nLR_RAMPUP_EPOCHS = 4\nLR_SUSTAIN_EPOCHS = 0\nEPOCHS = 25\n\ndef lrfn(epoch):\n    if epoch < LR_RAMPUP_EPOCHS:\n        lr = (LR_MAX - LR_START) / LR_RAMPUP_EPOCHS * epoch + LR_START\n    elif epoch < LR_RAMPUP_EPOCHS + LR_SUSTAIN_EPOCHS:\n        lr = LR_MAX\n    else:\n        decay_total_epochs = EPOCHS - LR_RAMPUP_EPOCHS - LR_SUSTAIN_EPOCHS - 1\n        decay_epoch_index = epoch - LR_RAMPUP_EPOCHS - LR_SUSTAIN_EPOCHS\n        phase = math.pi * decay_epoch_index / decay_total_epochs\n        cosine_decay = 0.5 * (1 + math.cos(phase))\n        lr = (LR_MAX - LR_MIN) * cosine_decay + LR_MIN\n    return lr\n\nrng = [i for i in range(EPOCHS)]\nlr_y = [lrfn(x) for x in rng]\nplt.figure(figsize=(10, 4))\nplt.plot(rng, lr_y)\nprint(\"Learning rate schedule: {:.3g} to {:.3g} to {:.3g}\". \\\n      format(lr_y[0], max(lr_y), lr_y[-1]))\n\n# # Training\n\ntf.keras.backend.clear_session()\n    \nTRAINING_STEPS = 85034//BATCH_SIZE\ntrain_ds = load_dataset_train(ALL_FILENAMES, batch_size=BATCH_SIZE, repeat=True, shuffle=True)\n\nwith strategy.scope():\n    \n    model = get_model_fpn()\n\n    opt = tf.keras.optimizers.AdamW(learning_rate=1e-5, weight_decay=1e-2)#, clipnorm=1.0)\n    opt.exclude_from_weight_decay(var_names=[\"layernorm\", \"layer_normalization\", \"LayerNorm\", \"layer_norm\", \"ln\", \"bn\", \"bias\"])\n\n    model.compile(loss=[tf.keras.losses.BinaryFocalCrossentropy(),\n                        tf.keras.losses.BinaryCrossentropy()],\n                  optimizer=opt,\n                  metrics=None)\n\nlr_callback = tf.keras.callbacks.LearningRateScheduler(lrfn, verbose=True)\n        \n_ = model.fit(train_ds,\n              steps_per_epoch=TRAINING_STEPS,\n              callbacks=[lr_callback],\n              epochs=EPOCHS)\n\nmodel.save_weights(f'model_efficientnet_fpn_10.h5')","metadata":{"_uuid":"5bdb1153-edf0-485c-b1d7-4096bf802833","_cell_guid":"d6781f21-c2be-4694-a290-ebdf20f85c59","collapsed":false,"jupyter":{"outputs_hidden":false},"trusted":true},"execution_count":null,"outputs":[]}]}