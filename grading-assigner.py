#!/usr/bin/env python
# -*- coding: utf-8 -*-
import signal
import sys
import argparse
import logging
import os
import requests
import time
import pytz
from dateutil import parser
from datetime import datetime, timedelta

import report_generator
import config

import pandas
import json

import subprocess
import pickle

utc = pytz.UTC

# Script config
BASE_URL = 'https://review-api.udacity.com/api/v1'
CERTS_URL = '{}/me/certifications.json'.format(BASE_URL)
ME_URL = '{}/me'.format(BASE_URL)
ME_REQUEST_URL = '{}/me/submission_requests.json'.format(BASE_URL)
CREATE_REQUEST_URL = '{}/submission_requests.json'.format(BASE_URL)
DELETE_URL_TMPL = '{}/submission_requests/{}.json'
GET_REQUEST_URL_TMPL = '{}/submission_requests/{}.json'
PUT_REQUEST_URL_TMPL = '{}/submission_requests/{}.json'
REFRESH_URL_TMPL = '{}/submission_requests/{}/refresh.json'
ASSIGNED_COUNT_URL = '{}/me/submissions/assigned_count.json'.format(BASE_URL)
ASSIGNED_URL = '{}/me/submissions/assigned.json'.format(BASE_URL)

REVIEW_URL = 'https://review.udacity.com/#!/submissions/{sid}'
REQUESTS_PER_SECOND = 1 # Please leave this alone.

logging.basicConfig(format='|%(asctime)s| %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

current_date = datetime.now().strftime('%Y-%m-%d')
headers = None

def signal_handler(signal, frame):
    if headers:
        logger.info('Cleaning up active request')
        me_resp = requests.get(ME_REQUEST_URL, headers=headers)
        if me_resp.status_code == 200 and len(me_resp.json()) > 0:
            logger.info(DELETE_URL_TMPL.format(BASE_URL, me_resp.json()[0]['id']))
            del_resp = requests.delete(DELETE_URL_TMPL.format(BASE_URL, me_resp.json()[0]['id']),
                                       headers=headers)
            logger.info(del_resp)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def alert_for_assignment(current_request, headers):
    if current_request and current_request['status'] == 'fulfilled':
        subprocess.call(['speech-dispatcher'])        #start speech dispatcher
        subprocess.call(['spd-say', '"Hello, you have been assigned to grade a new submission"'])
        logger.info("")
        logger.info("=================================================")
        logger.info("You have been assigned to grade a new submission!")
        logger.info("View it here: " + REVIEW_URL.format(sid=current_request['submission_id']))
        logger.info("=================================================")
        logger.info("Continuing to poll...")
        return None
    return current_request

def wait_for_assign_eligible():
    while True:
        assigned_resp = requests.get(ASSIGNED_COUNT_URL, headers=headers)
        if assigned_resp.status_code == 404 or assigned_resp.json()['assigned_count'] < 2:
            break
        else:
            logger.info('Waiting for assigned submissions < 2')
        # Wait 30 seconds before checking to see if < 2 open submissions
        # that is, waiting until a create submission request will be permitted
        time.sleep(30.0)

def refresh_request(current_request):
    logger.info('Refreshing existing request')
    refresh_resp = requests.put(REFRESH_URL_TMPL.format(BASE_URL, current_request['id']),
                                headers=headers)
    refresh_resp.raise_for_status()
    if refresh_resp.status_code == 404:
        logger.info('No active request was found/refreshed.  Loop and either wait for < 2 to be assigned or immediately create')
        return None
    else:
        return refresh_resp.json()

def fetch_certified_pairs(ids_queued=None):
    logger.info("Requesting certifications...")
    me_resp = requests.get(ME_URL, headers=headers)
    me_resp.raise_for_status()
    languages = me_resp.json()['application']['languages'] or ['en-us']

    certs_resp = requests.get(CERTS_URL, headers=headers)
    certs_resp.raise_for_status()

    certs = certs_resp.json()
    
    project_ids = [cert['project']['id'] for cert in certs if cert['status'] == 'certified']

    logger.info("Found certifications for project IDs: %s in languages %s",
                str(project_ids), str(languages))
    logger.info("Polling for new submissions...")
    
    projects_to_query(certs,ids_queued)
    
    proj_queued = [{'project_id': project_id, 'language': lang} for project_id in project_ids  for lang in languages]

    if ids_queued is not None:
        return [x for x in proj_queued if x['project_id'] in ids_queued]
    else:
        return proj_queued
    
def get_certifications(token):
    global headers
    headers = {'Authorization': token, 'Content-Length': '0'}
    logger.info("Requesting certifications...")
    me_resp = requests.get(ME_URL, headers=headers)
    me_resp.raise_for_status()
    languages = me_resp.json()['application']['languages'] or ['en-us']

    certs_resp = requests.get(CERTS_URL, headers=headers)
    certs_resp.raise_for_status()

    certifications = certs_resp.json()
    
    # project characteristics to retrieve:
    project_description = [u'status',u'id',u'price',u'name',u'hashtag']
    
    # retrieve project information:
    proj_info = {}
    
    for i,certi in enumerate(certifications):
        proj_info[i] = {}
        proj_info[i][u'status'] = certi[u'status']
        for field_proj in project_description[1:]:
            proj_info[i][field_proj] = certi['project'][field_proj]
        
    # Print in terminal all available projects:
    print "\n\nPROJECTS AVAILABLE:\n"
    print "{p[3]:^50} | {p[1]:^5} | {p[2]:^5} | {p[0]:^15} | {p[4]:^50}".format(p=project_description)
    for proj in  proj_info.keys():
        print "{p[name]:50} | {p[id]:^5} | {p[price]:^5} | {p[status]:^15} | {p[hashtag]:50}".format(p=proj_info[proj])
    

def projects_to_query(certifications,ids_queued=None):
    # project characteristics to retrieve:
    project_description = [u'status',u'id',u'price',u'name',u'hashtag']
    
    # retrieve project information:
    proj_info = {}
    
    for i,certi in enumerate(certifications):
        proj_info[i] = {}
        proj_info[i][u'status'] = certi[u'status']
        for field_proj in project_description[1:]:
            proj_info[i][field_proj] = certi['project'][field_proj]
          
    # Select just those projects selected by ids:
    if ids_queued is not None:
        print "\n\nSelected projects to queue:\n"
        print "{p[3]:^50} | {p[1]:^5} | {p[2]:^5} | {p[0]:^15} | {p[4]:^50}".format(p=project_description)
        for proj in  proj_info.keys():
            if proj_info[proj][u'id'] in ids_queued:
                print "{p[name]:50} | {p[id]:^5} | {p[price]:^5} | {p[status]:^15} | {p[hashtag]:50}".format(p=proj_info[proj])
        print "\n\n\n"
    else:
        print "\n All projects requested!\n"
        
def get_positions(certifications,ids_queue,curr_request_id):
    WAITS_URL = '{0}/submission_requests/{1}/waits.json'.format(BASE_URL,curr_request_id)
    wait_resp = requests.get(WAITS_URL, headers=headers)
    wait_resp.raise_for_status()
    waits = wait_resp.json()
    print waits
    
def retrieve_stats(token,start_date='2010-01-01',end_date=current_date):
    global headers
    headers = {'Authorization': token, 'Content-Length': '0'}
    logger.info("Requesting Projects information...")
    
    # retrieve projects completed:
    COMPLETED_URL_TMPL = '{0}/me/submissions/completed?start_date={1}&end_date={2}.json'.format(BASE_URL,start_date,end_date)
    completed_resp = requests.get(COMPLETED_URL_TMPL, headers=headers)
    completed_resp = completed_resp.json() if completed_resp.status_code == 200 else None
    #pickle.dump( completed_resp, open( "completed.pickle", "wb" ) )
    if completed_resp is None:
        print "We can't process your request: Response returns None, check your token, internet connection, etc."
        return
    
    # retrieve feedbacks:
    FEEDBACK_URL_TMPL = '{0}/me/student_feedbacks?start_date={1}&end_date={2}.json'.format(BASE_URL,start_date,end_date)
    fb_resp = requests.get(FEEDBACK_URL_TMPL, headers=headers)
    fb_resp = fb_resp.json() if fb_resp.status_code == 200 else None
    #pickle.dump( fb_resp, open( "fb.pickle", "wb" ) )
    
    #################################################################    
    ## Read input data:
    #################################################################
    #projects = pickle.load(open('/home/rafaelcastillo/Downloads/completed.pickle','rb'))
    dfproj = pandas.read_json(json.dumps(completed_resp))
    dfproj = dfproj.loc[:,[u'completed_at',u'project',u'price',u'status',u'id',u'is_training',u'result']]
    dfproj = dfproj.rename(columns={u'id':u'submission_id'})
    
    #fb = pickle.load(open('/home/rafaelcastillo/Downloads/fb.pickle','rb'))
    df_fb = pandas.read_json(json.dumps(fb_resp))
    df_fb = df_fb.loc[:,[u'submission_id',u'rating',u'body',u'created_at']]
    
    ## Merge both dataframes and do the required transformations to create plots and tables:
    df_all =  dfproj.merge(df_fb,how='left',on=u'submission_id')
    file_text, project_names,project_colors = report_generator.generate_report(df_all.copy())
    file_text = report_generator.generate_project_report(df_all.copy(),project_names,project_colors,file_text)
    file_text += report_generator.project_text_foot
    
    ## Save file:
    f = open(config.path_out + config.file_name + '.md','w')
    f.write(file_text)
    f.close()
    
    
    
def request_reviews(token,ids_queued=None):
    global headers
    headers = {'Authorization': token, 'Content-Length': '0'}

    project_language_pairs = fetch_certified_pairs(ids_queued)
    if len(project_language_pairs) == 0:
        print "No available projects to query. PROGRAM STOP"
        return
    logger.info("Will poll for projects/languages %s", str(project_language_pairs))
    
    me_req_resp = requests.get(ME_REQUEST_URL, headers=headers)
    current_request = me_req_resp.json()[0] if me_req_resp.status_code == 201 and len(me_req_resp.json()) > 0 else None
    

    if current_request:
        update_resp = requests.put(PUT_REQUEST_URL_TMPL.format(BASE_URL, current_request['id']),
                                   json={'projects': project_language_pairs}, headers=headers)
        current_request = update_resp.json() if update_resp.status_code == 200 else current_request

    while True:
        # Loop and wait until fewer than 2 reviews assigned, as creating
        # a request will fail
        wait_for_assign_eligible()

        if current_request is None:
            logger.info('Creating a request for ' + str(len(project_language_pairs)) +
                        ' possible project/language combinations')
            create_resp = requests.post(CREATE_REQUEST_URL,
                                        json={'projects': project_language_pairs},
                                        headers=headers)
            current_request = create_resp.json() if create_resp.status_code == 201 else None
        else:
            logger.info(current_request)
            closing_at = parser.parse(current_request['closed_at'])

            utcnow = datetime.utcnow()
            utcnow = utcnow.replace(tzinfo=pytz.utc)

            if closing_at < utcnow + timedelta(minutes=59):
                # Refreshing a request is more costly than just loading
                # and only needs to be done to ensure the request doesn't
                # expire (1 hour)
                logger.info('0-0-0-0-0-0-0-0-0-0- refreshing request 0-0-0-0-0-0-0')
                current_request = refresh_request(current_request)
            else:
                logger.info('Checking for new assignments')
                # If an assignment has been made since status was last checked,
                # the request record will no longer be 'fulfilled'
                url = GET_REQUEST_URL_TMPL.format(BASE_URL, current_request['id'])
                get_req_resp = requests.get(url, headers=headers)
                current_request = get_req_resp.json() if me_req_resp.status_code == 200 else None

        current_request = alert_for_assignment(current_request, headers)
        if current_request:
            # Wait 2 minutes before next check to see if the request has been fulfilled
            time.sleep(120.0)
    
if __name__ == "__main__":
    cmd_parser = argparse.ArgumentParser(description =
    "Poll the Udacity reviews API to claim projects to review."
    )
    cmd_parser.add_argument('--auth-token', '-T', dest='token',
    metavar='TOKEN', type=str,
    action='store', default=os.environ.get('UDACITY_AUTH_TOKEN'),
    help="""
        Your Udacity auth token. To obtain, login to review.udacity.com, open the Javascript console, and copy the output of `JSON.parse(localStorage.currentUser).token`.  This can also be stored in the environment variable UDACITY_AUTH_TOKEN.
    """
    )
    cmd_parser.add_argument('--debug', '-d', action='store_true', help='Turn on debug statements.')
    cmd_parser.add_argument('--certification', '-c', action='store_true', help='Retrieve current certifications.')
    cmd_parser.add_argument('--ids', '-ids', help='Projects ids to queue separated by spaces, i.e.: -ids 28 38 139', dest='ids_queued', nargs='+', type=int, default=config.ids_queued)
    cmd_parser.add_argument('--stats', '-stats', action='store_true', help='Retrieve stats for all projects')
    args = cmd_parser.parse_args()

    if not args.token:
        cmd_parser.print_help()
        cmd_parser.exit()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        
    if args.certification:
        get_certifications(args.token)
    elif args.stats:
        retrieve_stats(args.token)   
    else:    
        request_reviews(args.token, args.ids_queued)
