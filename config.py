'''
Created on Oct 15, 2016

@author: rafaelcastillo
'''
import os

user_token = ''

# Assign token
os.environ["UDACITY_AUTH_TOKEN"] = user_token

# Select default project ids:
ids_queued = []

# Define path to output report:
path_out = ''

# Report filename
file_name = 'reviewer_report' # extensions is not required, as it is .md