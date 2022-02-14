#!/usr/bin/env python3

import sys
import os
import pandas as pd
import argparse
from keras import backend as Kbackend
from keras import callbacks as Kcallbacks
from keras import optimizers as Koptimizers
from keras import losses as Klosses
from keras import models as Kmodels
from keras import backend as Kbackend
from keras import applications as Kapplications
from keras import layers as Klayers

from lib import analysis_utils as au
from lib import transforms as transforms

class Annotator:
    """
    Will annotate images given `model` and a set of image names.
    """

    def __init__(self, model):
        """
        Initialize Annotator class by providing a *.hdf5 model file and a set of 
        image names.

        Args:
            `model` the *.hdf5 model file to use for annotation.
        """
        self.model = model

    def get_generator(
        self,
        df,
        path=None,
        batch_size=2,
        transformations = [
            transforms.resize,
            transforms.centerCrop,
            transforms.normalizeMinMax,
            transforms.normalizeStandardScore
        ]
    ):
        """
        returns a generator instance over the dataframe `df`
        
        Args:
            `df`: The dataframe to generate batches from
            `batch_size`: Size of batches to generate

        Returns:
            A Keras sequence generator object.
        """
        return au.ResizeSequence(
            df,
            batch_size=batch_size, 
            targets = [],
            image_dir=path,
            transforms=transformations,
        )

    def get_image_df(self, images, path=None, column=None):
        """
        Returns a dataframe based on csv file path given by `images`

        Args:
            `images`: Filepath to images csv file.

        Returns:
            A Pandas DataFrame
        """
        path = path or ""
        df = pd.read_csv(images)
        image_col = None
        if not column is None:
            image_col = column
        elif len(df.columns) == 1:
            image_col = df.columns[0]
        else:
            for c in df.columns:
                if not type(df[c].sample(1).values[0]) == str:
                    continue
                if os.path.isfile(
                    os.path.join(path, df[c].sample(1).values[0])
                ):
                    image_col = c
                    break
        if image_col is None:
            raise ValueError(
                "Could not find column corresponding to image names in CSV file" %
                images
            )

        return df.rename(columns={"image_name": "name"})

    def annotate(self, df, generator, path=None, column=None, model=None):
        """
        Annotate images using model.
        Args:
            `images` a csv file where one column must indicate the names of the images
                     if `path` is not provided, then the image names must include the
                     path as well.
            `model` model to use, if not provided will use the one set for the
                    object (optional).
        Returns:
            The list of images and their associated score as provided by the model.
        """
        model_path = model or self.model

        img_input = Klayers.Input(
            shape=(224,224,3),
            name='img_input'
        )

        resnet_model = Kapplications.ResNet50(include_top=False, weights='imagenet')(img_input)

        flatten = Klayers.Flatten()(resnet_model)

        fully_connected_violence = Klayers.Dense(1000, activation='relu')(flatten)
        dropout_violence = Klayers.Dropout(.5)(fully_connected_violence)
        violence_out = Klayers.Dense(
            1,
            activation='sigmoid',
            name='violence_out'
        )(dropout_violence)

        fully_connected_protest = Klayers.Dense(1000, activation= 'relu')(flatten)
        dropout_protest = Klayers.Dropout(.5)(fully_connected_protest)
        protest_out = Klayers.Dense(
            1,
            activation='sigmoid',
            name='protest_out'
        )(dropout_protest)

        model = Kmodels.Model(inputs= img_input, outputs=[protest_out, violence_out])
        model.load_weights(model_path)

        preds = model.predict_generator(generator, verbose = 1)
        preds_protest = preds[0][:len(df)]   # Generator will wrap, 
        preds_violence = preds[1][:len(df)]  # so we avoid getting more than N predictions.

        return preds_protest, preds_violence


#################################### RUN #########################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-m",
        "--model",
        help="The model to use",
    )
    parser.add_argument(
        "-f",
        "--data",
        help="The datafile with image names"
    )
    parser.add_argument(
        "-p",
        "--image-path",
        default="./dumps/",
        help="Path to directory with images",
    )
    parser.add_argument(
        "-b",
        "--batch-size",
        type=int,
        default=2,
        help="The size of each batch"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="annotated.csv",
        help="Name of output csv file (Default: annotated.csv)",
    )

    args = parser.parse_args()

    missing_images = pd.read_csv("missing_images.csv")

    anno = Annotator(model=args.model)
    df = anno.get_image_df(args.data, path=args.image_path)
    # disregard rows with missing images: (for now)
    df = df[~df.name.isin(missing_images.image_name)]
    generator = anno.get_generator(df, path=args.image_path, batch_size=args.batch_size)

    preds_protest, preds_violence = anno.annotate(df=df, generator=generator, path="./dumps")
    print(
        "protest shape is ",
        preds_protest.shape,
        " violence shape is ",
        preds_violence.shape
    )

    results = df.copy()[:len(preds_protest)]
    results["pred_protest"] = preds_protest
    results["pred_violence"] = preds_violence
    print(results)

    results.to_csv(args.output)
