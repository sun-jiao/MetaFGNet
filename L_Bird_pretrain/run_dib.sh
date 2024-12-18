#!/bin/bash
python main.py --batch_size 256 --momentum 0.9 --weight_decay 1e-4 --data_path /root/autodl-tmp/dib/ --dataset dongniao \
               --pretrain --freeze --print_freq 1 --epochs 32 --schedule 15 23 --newfc --numclass_old 10320 --numclass_new 11000  --workers 64 \
               --pretrained_model /root/autodl-tmp/LBird-31_checkpoint.pth.tar --resume /root/autodl-tmp/LBird-31_checkpoint.pth.tar


