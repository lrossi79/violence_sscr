# Image scraping and prediction
This project defines a scraper for images in tweets, as well as a script for loading up a pre-trained model to use for prediction of each image.

These are mainly contained in `scraper.py` and `classify.py`. A last scraper was built to find what original tweets were associated with the retweets from the G20 protests. This scraper is written in `retweets_association.py` and the corresponding datafile is in `retweets_association.csv`. All 3 python files includes a full CLI, in order to see possible parameters run either with `-h` or `--help`, e.g. 
```
  python3 classify.py --help
```
## Setup

Clone this project and add the image files into a subfolder (or redownload them using `scraper.py`). Then from the project root folder run:
```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

# The Code and the Data

A brief introduction to the code and datafiles in this project is here. First the python files:

| Filename      | Brief Description     |
|---            |---                    |
| `scraper.py`  | Scrapes images off of tweets |
| `classify.py` | Given a model and a set of images, will create dataset of model predictions. |
| `retweets_association.py` | Builds dataset of association between retweets and what tweet was retweeted. |
| `find_missing.py` | A python program to check if all images in a dataset also exists in a dumps folder |

The datafiles are described in the following: 

| Filename      | Brief Description     |
|---            |---                    |
| `annotated.csv` | All images annotated by the model (Images from both tweets and retweets). |
| `suspended_accounts.csv` | A set of post links that redirects to `https://twitter.com/account/suspended` (Note: contains duplicates) |
| `failed_resources.csv` | A set of post links along with their response code, most of which were 404 indicating that the poster has since deleted the tweet (Note: contains duplicates) |
| `retweet_assocation.csv` | Each row is a retweet along with the username and username of the original post as well as links to both. |
| `tweets_images.csv` | The initial output from the scraper, that is, it is similar to `annotated.csv` but without the predictions. |
| `missing_images.csv` | The names of 16 images that were assumed downloaded, but did not exists, however this has since been fixed. |

## `Annotated.csv`

Rows are:
  - `tweet_num`: a simple counter, since every row is an image, every image with the same `tweet_num` came from the same tweet. 
  - `tweet_type`: Taken from the original dataset, is either `tweet`, `retweet` or `reply`. By design all the ones included in this dataset are of either `tweet` or `retweet`.
  - `post_link`: Link to the post
  - `name`: Name of image file without any prefixed path specification.
  - `pred_protest`: Probability given by the model that the image is protest related.
  - `pred_violence`: Probability given by the model that the image is perceived more violent than other images.

## `retweet_association.csv`

Rows are:
  - `tweet_num`: Simple counter, similar properties as for `annoated.csv` and `retweets_annotated.csv`
  - `tweet_type`: Similar as previous section. 
  - `retweeters_username`: Username extracted from the URL of the retweeter.
  - `orig_username`: The username of the person being retweeted as extracted by the URL.
  - `post_link`: Link to the retweet.
  - `retweeted_from`: Link to the original tweet.

## `Suspended accounts.csv` and `failed_resources.csv`

The `suspended_accounts.csv` contains links of any resource that redirects to `https://twitter.com/account/suspended`.

Similarly, the `failed_resources.csv` contains links of resources where the HTTP response code was different from 200. Most typical, the response code was 404 Not Found for links to tweets that has since been deleted. A few others has responded with 503 Service Unavailable, which indicates some connection problem to the Twitter servers, possibly a throttling imposed by Twitter and a suspequent connection timeout thrown by the scraper. This can only really be guessed, fortunately, there are only few of such cases.

**Note**: because of several different runs, including retweets pointing to the same original tweet, this dataset contains duplicates
