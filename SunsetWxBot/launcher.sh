#!/bin/sh
# launcher.sh
## Navigate to root directory, then to this directory, then execute script and go back to root

cd /
cd home/pi/Documents/twitterbots/SunsetWxBot
. /home/pi/miniconda3/etc/profile.d/conda.sh
conda activate sunsetwx
python tweet_updates.py
cd /

