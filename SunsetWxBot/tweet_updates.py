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
    
    def __init__(self, location, type, log_df = TWEET_HISTORY_DF):
        """
        Instantiate the class with the following parameters.
        
        :param location (str): Name of the location
        """
        self.location = location
        self.type = type
        self.lat = c.LOCATIONS[self.location]['lat']
        self.lon = c.LOCATIONS[self.location]['lon']
        self.sunsetwx_response = py_sunsetwx.get_quality(self.lat, self.lon, self.type)
        self.log_df = log_df    
        
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
        Method to send tweets conditional upon the sunset/sunrise being nice enough.
        
        Returns: None
        """
        
        ## Check the quality/score
        quality = self.sunsetwx_response['features'][0]['properties']['quality']
        score = self.sunsetwx_response['features'][0]['properties']['quality_percent']
        
        ## For great ones... compose a status
        if quality == 'Great':
            
            local_time_str = self.time_converted.strftime("%I:%M %p")
            if self.type == 'sunrise':
                time_of_day_str = 'tomorrow morning'
            elif self.type == 'sunset':
                time_of_day_str = 'this evening'
            status = f'Looks like there will be a great {self.type} in {self.location} {time_of_day_str}!  Check it out at {local_time_str}.'
            
            ## Post about the great ones
            api.update_status(status=status)
        
        ## Update the log regardless
        self.update_log_record(datetime.today().strftime("%Y-%m-%d"), score)
    
    
    def update_log_record(self, current_date, score):
        """
        Update the log_df attribute for the given record.
        
        :param current_date (str): Current date in %Y-%m-%d format
        :param score (float): Quality score/percent out of 100
        
        Returns: None
        """
        
        ## Find the relevant index
        log_index = list(self.log_df[((self.log_df['city'] == self.location) & 
                                 (self.log_df['type'] == self.type))].index)[0]
        
        ## Update last run date
        self.log_df.loc[log_index, 'last_run_dt'] = current_date
        
        ## Update the record's quality category counts
        if score < 25:
            self.log_df.loc[log_index, 'n_poor'] = self.log_df['n_poor'][log_index]+1
        elif score < 50:
            self.log_df.loc[log_index, 'n_fair'] = self.log_df['n_fair'][log_index]+1
        elif score < 75:
            self.log_df.loc[log_index, 'n_good'] = self.log_df['n_good'][log_index]+1
        else:
            self.log_df[log_index, 'n_great'] = self.log_df['n_great'][log_index]+1
        
        ## Update the average quality score and n_runs
        self.log_df.loc[log_index, 'avg_quality_score'] = ((self.log_df['avg_quality_score'][log_index]*
                                                            self.log_df['n_runs'][log_index] + 
                                                            score)/(self.log_df['n_runs'][log_index]+1))
        self.log_df.loc[log_index, 'n_runs'] = self.log_df['n_runs'][log_index]+1


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
    
    ## Iterate through the time series and states
    log_df = TWEET_HISTORY_DF.copy()
    for loc in c.LOCATIONS.keys():
            
        ## Instantiate a class to do the tweetin'
        MySunTweeter = SunTweeter(loc, type, log_df)
        MySunTweeter.send_tweet()
        
        ## Save the log to use in the next iteration of the loop
        log_df = MySunTweeter.log_df
    
    ## Overwrite the log with the updated records
    log_df.to_csv("log/SunsetWx_full_tweet_log.csv",
                       index = False)


if __name__ == "__main__":
    main()
