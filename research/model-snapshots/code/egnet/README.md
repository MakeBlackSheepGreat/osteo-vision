# EGNet-pytorch

### Prerequisites
Ubuntu 18.04\
Python==3.8.2\
Torch==2.41+cu118\
Torchvision==0.9.1+cu118\


### Dataset
For all datasets, they should be organized in below's fashion:
```
|__dataset_name
   |__train
      |__images xxx.jpg ...
      |__masks xxx.jpg ...
   |__test
      |__images xxx.jpg ...
      |__masks xxx.jpg ...
```
For training, put your dataset folder under:
```
dataset/
```

### Train & Test
**Make sure you have enough GPU RAM**.\
With default setting (batchsize=64), 32GB RAM is required, but you can always reduce the batchsize to fit your hardware.

Please download the ISIC17&18 dataset from [[EGE-UNet]](https://github.com/JCruan519/EGE-UNet)

download the BUSI&ISIC16 dataset[[Data]](https://drive.google.com/drive/folders/1mkhDlJSaE3H92va7UJKbFt2v_dcWzYWm?usp=sharing)

Download the pre-trained PVT-V2 model 'PVT-V2-B2' from [[PVT-V2]](https://github.com/whai362/PVT/tree/v2/classification) and put it in the '/model/pretrain' folder

Default values in option.py are already set to the same configuration as our paper, so \
after setting the ```--dataset_root``` flag in **option.py**, to train the model (default dataset: ISIC2017), simply:

```
python main.py --GPU_ID 0 --dataset_root （Your file path）
```
to test the model located in the **ckpt** folder (default dataset: ISIC2018), simply:
```
python main.py --test_only --pretrain "isic17.pt" --GPU_ID 0 --dataset_root （Your file path）
```
If you want to train/test with different settings, please refer to **option.py** for more control options.\
Currently only support training on single GPU.

### Pretrain Model & Pre-calculated Saliency Map
When testing, you need to download the pre-trained model. Pretrained models can be downloaded from [[Google Drive]](https://drive.google.com/drive/folders/1yuEzi_afvnCfzY5Ew-QRCxmnTIzT9EDO?usp=sharing)

