#!/usr/bin/env python3

import os
import pandas as pd
from imageio import imread

df = pd.read_csv("tweets_images.csv")

missing = ["tweet", "image_name"]
for _, item in df.iterrows():
    try:
        imread(os.path.join("dumps", item.image_name))
    except Exception as e:
        missing.append([item.post_link, item.image_name])
