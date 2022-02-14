#!/usr/bin/env python3
# This scraper aims at requesting the resources from `post_link`
# for tweets of `post_type` == "retweet", to build their association
# with original tweets.

import os
import csv
import re
import argparse
import asyncio
import aiohttp
import pandas as pd
from functools import reduce

# from local:
from scraper import Scraper

class RetweetScraper(Scraper):

    async def scrape_tweet(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.head(url, allow_redirects=True) as response:
                # Return url of the retweet, along with response url wich is the
                # tweet it retweeted:
                # print(url, response.url)
                return url, response.url

    def create_data(self, flush_interval=20, batchsize=30):
        header = [
            "tweet_num",
            "tweet_type",
            "retweeters_username",
            "orig_username",
            "post_link",
            "retweeted_from"
        ]

        if hasattr(self, "offset"):
            build_data = []
        else:
            build_data = [header]

        n = 1
        for index, items in self.iter_data(batchsize=batchsize, post_type="retweet"):
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

            for i, t in enumerate(tweet_tasks):
                orig_url = t.result()[0]
                retweeted = t.result()[1]
                row = [
                    index + i,
                    "retweet",
                    self.parse_twitter_username(orig_url),
                    self.parse_twitter_username(retweeted),
                    orig_url,
                    retweeted,
                ]
                build_data.append(row)

            if n % flush_interval == 0:
                with open(self.output, "a") as f:
                    writer = csv.writer(f)
                    writer.writerows(build_data)
                    build_data = []

            n += 1
            #if n > 10:
            #    break

        with open(self.output, "a") as f:
            writer = csv.writer(f)
            writer.writerows(build_data)
            build_data = []

        return build_data

    def parse_twitter_username(self, url):
        """ Given a tweet url, returns the username """
        if not hasattr(self, "username_pattern"):
            setattr(
                self,
                "username_pattern",
                re.compile("twitter.com/([a-zA-Z0-9_]+)")
            )
        if "account/suspended" in str(url):
            return "N/A Suspended"
        return self.username_pattern.findall(str(url))[0]

################################################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A scraper to associate retweets with original tweets"         
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
        help="Filename to output to (Default: 'output.csv')"
    )
    parser.add_argument(
        "-i",
        "--flush-interval",
        default=20,
        type=int,
        help="How many tweets to fetch before flushing to file (Default: 20)"
    )
    parser.add_argument(
        "-b",
        "--batchsize",
        default=20,
        type=int,
        help="How many tweets to fetch asynchronously in one batch (Default: 20)"
    )
    
    args = vars(parser.parse_args())

    if os.path.exists(args["output"]):
        # If output already exists, will resume job with an offset of the
        # highest `tweet num` in file:
        try:
            args["offset"] = pd.read_csv(args["output"]).tweet_num.max()
        except:
            pass 

    scraper = RetweetScraper(**args)
    scraper.create_data(
        flush_interval=args["flush_interval"],
        batchsize=args["batchsize"]
    )
