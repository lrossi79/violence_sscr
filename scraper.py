#!/usr/bin/env python3

import argparse
import re
import os
import time
import csv
import asyncio
import aiohttp
from functools import reduce
import requests as req
import pandas as pd
from bs4 import BeautifulSoup as bs

regex = re.compile("\/|:")

class Scraper:

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

        self.read_data()
    
    def read_data(self):
        self.data = pd.read_csv(self.filename)

    def iter_data(self, data=None, batchsize=1, offset=0, post_type="retweet"):
        data = data or self.data
        if type(post_type) == str:
            data = data[data.post_type == post_type]
        else:
            data = data[data.post_type.isin(post_type)]
        self.datalength = len(data)
        if hasattr(self, "offset"):
            offset = int(self.offset)
        index = offset + 1
        while index < len(data):
            end = index + batchsize
            items = data.iloc[index:end]

            yield index, items
            index += batchsize


    async def scrape_tweet(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, allow_redirects=True) as response:
                tw_body = await response.text()
                if str(response.url) == "https://twitter.com/account/suspended":
                    with open("suspended_accounts.csv", "a") as f:
                        f.write("%s\n" % url)
                    return [] 
                if response.status != 200:
                    with open("failed_resources.csv", "a") as f:
                        f.write("%s,%s\n" % (response.status, url))
                    return [] 

                soup = bs(tw_body, 'lxml').find(class_="permalink-container")
                if soup is None:
                    return []

                dumps_images = soup.find_all("img", {'data-aria-label-part': True})
                for tag in soup.find_all("meta"):
                    if not "property" in tag.attrs:
                        continue
                    if "twitter:image" == tag.attrs['property'] or "og:image" == tag.attrs['property']:
                        if not "profile_images" in tag.attrs["content"]:
                            dumps_images.append(tag.attrs['content'])

                print("Length of dumps_images: %s from %s" % (len(dumps_images), url))

                if not dumps_images:
                    return []

                return url, dumps_images

    def scrape_tweet_images(self, img_urls, dump_to="./dumps", quadratic_backoff=.1): 
        names = []
        prev = {}
        for index, img in enumerate(img_urls):
            if type(img) != str:
                img_url = img['src']
            else:
                img_url = img

            name = regex.sub('_', img_url)
            name = name.replace("jpg_large", "jpg")

            if name in prev:
                continue
            if os.path.exists(os.path.join(dump_to, name)):
                print("Found existing")
                continue

            names.append(name)
            prev[name] = True # ensure we dont do the same work more than once
            if not dump_to is None:
                if os.path.isfile(os.path.join(dump_to, name)):
                    continue
            time.sleep(quadratic_backoff) # wait `quadratic_backoff` sec between each requests
            print("Getting image: %s" % name)

            img_res = req.get(img_url)

            if not dump_to is None:
                with open(os.path.join(dump_to, name), 'wb') as f:
                    for chunk in img_res:
                        f.write(chunk)

        return names


    def create_row(self, tweet_num, image_path, row):
        return list(map(lambda x: str(x).strip(), [
            tweet_num,
            row.post_type,
            row.post_link,
            image_path
        ]))
 
    def create_data(self, flush_interval=120, batchsize=30):
        header = ["tweet_num", "tweet_type", "post_link", "image_name"]
        if hasattr(self, "offset"):
            build_data = []
        else:
            build_data = [header]

        n = 1
        for index, items in self.iter_data(batchsize=batchsize):
            print("_" * 20 + "\tTweets: %s-%s [%.2f%%]\t" % (
                    index,
                    index+batchsize,
                    index/self.datalength * 100
                ) + "_" * 20)

            post_links = items.post_link.tolist()

            futures = list(map(
                self.scrape_tweet,
                post_links
            ))
            
            loop = asyncio.get_event_loop()
            tweet_tasks = reduce(
                lambda x, y: x + list(y),
                loop.run_until_complete(asyncio.wait(futures)),
                []
            )

            image_names = []
            for tweet_and_images in filter(lambda x: len(x) > 0, map(lambda x: x.result(), tweet_tasks)):
                try:
                    tweet_url = tweet_and_images[0]
                    image_set = tweet_and_images[1]
                except:
                    print("Failed to unpack", tweet_and_images)
                    continue
                res = self.scrape_tweet_images(image_set)
                image_names.append((tweet_url, res))

            offset = 0
            for tweet_url, images in image_names:
                if images is None:
                    offset += 1
                    continue
                for img_path in images:
                    build_data.append(
                        self.create_row(
                            index + offset, # we cannot just use index,
                                            #since we receive index + batchsize
                            img_path, 
                            items[items.post_link == tweet_url].iloc[0]
                        )
                    )

                offset += 1

            if n % flush_interval == 0:
                with open(self.output, "a") as f:
                    writer = csv.writer(f)
                    writer.writerows(build_data)
                    build_data = []
            n += 1

        with open(self.output, "a") as f:
            writer = csv.writer(f)
            writer.writerows(build_data)
            build_data = []

        return build_data

 
################################################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape images off of twitter based on twitter data dump"
    )

    parser.add_argument(
        "-f",
        "--filename",
        help="The filename of the csv data file"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output.csv",
        help="Filename to output to (Default: output.csv)"
    )
    parser.add_argument(
        "-i",
        "--flush-interval",
        default=10,
        type=int,
        help="Define how many batches to fetch before flushing to file (default: 10)"
    )
    parser.add_argument(
        "-b",
        "--batchsize",
        default=20,
        type=int,
        help="How many tweets to fetch asynchronously in one batch (default: 20)"
    )

    args = vars(parser.parse_args())

    if os.path.exists(args["output"]):
        # If output already exists, will resume job with an offset of the
        # highest `tweet num` in file:
        args["offset"] = pd.read_csv(args["output"]).tweet_num.max()


    scraper = Scraper(**args)
    scraper.create_data(flush_interval=args["flush_interval"], batchsize=args["batchsize"])
