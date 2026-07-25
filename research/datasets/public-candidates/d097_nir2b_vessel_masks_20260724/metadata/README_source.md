# Deep Learning-Assisted NIR-IIb sO₂ Imaging

This repository contains code for training a U-Net model to segment intestinal vasculature in near-infrared IIb (NIR-IIb; 1500-1700 nm) images, and reconstruct blood oxyhemoglobin saturation (sO₂) maps from dual-excitation imaging data.

## Features
- U-Net-based segmentation of vascular structures
- Binary classification of vessels from grayscale TIFF stacks
- Data augmentation using Albumentations
- Dice score tracking and visualization
- Compatible with NIR-IIb imaging experiments

## Folder Structure
├── model.py # U-Net definition

├── train.py # Training script

├── dataset.py # Data loader

├── utils.py # Helper functions

├── apply.py # Apply U-Net

├── gut (closed + opened belly)_images_train/ # input train TIFFs

├── gut (closed + opened belly)_images_val/ # input validation TIFFs

├── gut (closed + opened belly)_masks_train/ # mask train TIFFs

├── gut (closed + opened belly)_masks_val/ # mask validation TIFFs

├── requirements.txt # Dependencies

├── README.md # This file

## Setup
```bash
pip install -r requirements.txt
