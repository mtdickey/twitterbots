# -*- coding: utf-8 -*-
"""

Twitterbot for @DMV_COVID19.  

Tweets daily updates on trends in DC, Maryland, and Virginia COVID-19 data.

@author: Michael Dickey

"""

## Essential packages
import os
import io
import pytz
import requests
import numpy as np
import pandas as pd
from twython import Twython
from datetime import datetime

## Twitter API keys and access info
import tweet_config as c

## SunsetWx API wrapper
from pysunsetwx import PySunsetWx
py_sunsetwx = PySunsetWx(c.sunsetwx_email, c.sunsetwx_password)

## Log
TWEET_HISTORY_DF = pd.read_csv("log/SunsetWx_full_tweet_log.csv")

### Connect to Twitter API
api = Twython(c.api_key,
              c.api_secret,
              c.access_token,
              c.access_token_secret)

class SunTweeter():
    """
    The SunTweeter class contains methods for gathering sunrise/sunset data from SunsetWx composing tweets.
    """
    
    def __init__(self, location, type):
        """
        Instantiate the class with the following parameters.
        
        :param location (str): Name of the location
        """
        self.location = location
        self.type = type
        self.lat = c.LOCATIONS[self.location]['lat']
        self.lon = c.LOCATIONS[self.location]['lon']
        self.sunsetwx_response = py_sunsetwx.get_quality(self.lat, self.lon, self.type)
        self.log_df = None    
        
        ## Find the time of the sunrise/sunset
        #### Lookup civil time of "dawn" if sunrise, "dusk" if sunset
        if type == 'sunrise':
            self.dawn_dusk = 'dawn'
        elif type == 'sunset':
            self.dawn_dusk = 'dusk'
        self.utc_time = pytz.utc.localize(datetime.strptime(self.sunsetwx_response['features'][0]['properties'][self.dawn_dusk]['civil'], '%Y-%m-%dT%H:%M:%SZ'))
        self.time_converted = self.utc_time.astimezone(pytz.timezone(c.LOCATIONS[location]['timezone']))
        
    def send_tweet(self):
        """
        Method to send tweets conditional upon the sunset/sunrise being nice enough
        
        """
        
        ## Check the quality
        quality = self.sunsetwx_response['features'][0]['properties']['quality']
                
        if quality == 'Great':
            
            local_time_str = self.time_converted.strftime("%I:%M %p")
            if self.type == 'sunrise':
                time_of_day_str = 'tomorrow morning'
            elif self.type == 'sunset':
                time_of_day_str = 'this evening'
            status = f'Looks like there will be a great {self.type} in {self.location} {time_of_day_str}!  Check it out at {local_time_str}.'
            
            ## Get the quality score in case we want it for post-hoc analysis
            score = self.sunsetwx_response['features'][0]['properties']['quality_percent']
            
            ## Post it and log it
            api.update_status(status=status)
            self.new_tweet_log(status, datetime.today().strftime("%Y-%m-%d"), score)
    
    
    def new_tweet_log(self, status, current_date, score):
        """
        Take in tweet metadata and add it to the log.
        """
        
        ## Logging tweets sent
        tweets_sent = pd.DataFrame({'status': [status],
                                    'date': [current_date],
                                    'location': [self.location],
                                    'quality_score': [score]})
        
        ## Append if there's an existing DF in the log    
        if self.log_df is not None:
            log_df = self.log_df.append(tweets_sent)
        else:
            log_df = tweets_sent
        
        self.log_df = log_df
        return log_df


def main():
    """
    Run the whole way through and send tweets for all states and series when necessary.
    """
    
    ## Determine whether to query for the sunset or sunrise
    if datetime.now().hour >= 20:
        ## Run sunrise tweets after 8PM
        type = 'sunrise'
    else:
        ## Any earlier, run sunset tweets (by default run at 12PM)
        type = 'sunset'
    
    logs = []    
    ## Iterate through the time series and states
    for loc in c.LOCATIONS.keys():
            
        ## Instantiate a class to do the tweetin'
        MySunTweeter = SunTweeter(loc, type)
        MySunTweeter.send_tweet()
        
        if MySunTweeter.log_df is not None:
            ## If there was a tweet logged, add it to the list
            logs.append(MySunTweeter.log_df)
    
    if len(logs) > 0:
        tweets_sent_df = pd.concat(logs)
        tweets_sent_df.to_csv(f"log/tweet_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv",
                              index = False)
        new_log_df = pd.concat([TWEET_HISTORY_DF, tweets_sent_df], sort = False)
        new_log_df.to_csv("log/SunsetWx_full_tweet_log.csv",
                          index = False)


if __name__ == "__main__":
    main()
