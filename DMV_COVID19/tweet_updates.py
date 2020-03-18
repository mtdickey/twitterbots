# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns; sns.set(color_codes=True)
from datetime import datetime

### Read in current data
confirmed_df = pd.read_csv("https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Confirmed.csv")
deaths_df    = pd.read_csv("https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Deaths.csv")
recovered_df = pd.read_csv("https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_19-covid-Recovered.csv")
dfs = {'Confirmed': confirmed_df, 
       'Deaths': deaths_df,
       'Recovered': recovered_df}

### States of interest
STATES = ['District of Columbia', 'Maryland', 'Virginia']


def tidy_timeseries(data, location, series_name):
    
    tidy_df = (data[data['Province/State'] == location]
                  .melt(id_vars = ['Province/State', 'Country/Region',
                                   'Lat', 'Long'], var_name = 'Date',
                        value_name = series_name)
                  .rename(columns = {'Date':'date_str'}))
    
    tidy_df['Date'] = tidy_df['date_str'].apply(lambda x: datetime.strptime(x, "%m/%d/%y"))
    
    ## Only include after March 1, 2020 for these states
    tidy_df = tidy_df[tidy_df['Date'] > datetime(2020, 2, 29)]
    
    return tidy_df


def plot_timeseries(data, location, series_name):
    
    ## Initialize lineplot
    plt.figure(figsize=(10,5))
    chart = plt.figure(figsize=(10,5))
    
    ## Plot the data and rotate date axis labels
    chart = sns.lineplot(x="Date", y=series_name, data=data)
    plt.xticks(rotation=30)
    
    ## Most recent date
    update_dt = data['Date'].max().strftime("%Y-%m-%d")
    update_dt_title = data['Date'].max().strftime("%b. %d, %Y")
    
    ## Set the title depending on location, series name, and recent date
    if series_name == 'Confirmed':
        series_title = 'Number of Confirmed COVID-19 Cases'
    elif series_name == 'Deaths':
        series_title = 'Number of COVID-19 Deaths'
    elif series_name == 'Recovered':
        series_title = 'Number of COVID-19 Recoveries'
    plt.title(f'{series_title} in {location}\nAs of {update_dt_title}')
    filename = f'plots/{location}_{series_name}_{update_dt}.png'
    plt.savefig(filename)
    
    return filename


def main():
    
    plots = []
    for series in dfs:
        for loc in STATES:
            ts_df = tidy_timeseries(dfs[series], loc, series)
            if ts_df[series].max() > 0:
                plot_name = plot_timeseries(ts_df, loc, series)
                plots.append(plot_name)
                
    ### Tweet:
    #for plot in plots:
    #    api.update_with_media(plot, status=f'')
    
if __name__ == "__main__":
    main()