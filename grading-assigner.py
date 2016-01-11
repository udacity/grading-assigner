#!/usr/bin/env python
import argparse
import itertools
import logging
import os
import requests
import time

# Script config
CERTS_URL = 'http://review-api.udacity.com/api/v1/me/certifications.json'
ASSIGN_URL = 'http://review-api.udacity.com/api/v1/projects/{pid}/submissions/assign.json'
REVIEW_URL = 'http://review.udacity.com/#!/submissions/{sid}'
REQUESTS_PER_SECOND = 1 # Please leave this alone.

logging.basicConfig(format = '|%(asctime)s| %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def request_reviews(token):
    headers = {'Authorization': token, 'Content-Length': '0'}

    logger.info("Requesting certifications...")
    certs = requests.get(CERTS_URL, headers=headers).json()
    project_ids = [cert['project']['id'] for cert in certs if cert['status'] == 'certified']

    logger.info("Found certifications for project IDs: {}".format(str(project_ids)))
    logger.info("Polling for new submissions...")

    for pid in itertools.cycle(project_ids):
        resp = requests.post(ASSIGN_URL.format(pid = pid), headers=headers)
        if resp.status_code == requests.codes.created:
            submission = resp.json()

            logger.info("")
            logger.info("=================================================")
            logger.info("You have been assigned to grade a new submission!")
            logger.info("View it here: " + REVIEW_URL.format(sid = submission['id']))
            logger.info("=================================================")
            logger.info("Continuing to poll...")

        time.sleep(1.0 / REQUESTS_PER_SECOND)


if __name__=="__main__":
    parser = argparse.ArgumentParser(description =
	"Poll the Udacity reviews API to claim projects to review."
    )
    parser.add_argument('--auth-token', '-T', dest='token',
	metavar='TOKEN', type=str,
	action='store', default=os.environ.get('UDACITY_AUTH_TOKEN'),
	help="""
	    Your Udacity auth token. To obtain, login to review.udacity.com, open the Javascript console, and copy the output of `JSON.parse(localStorage.currentUser).token`.  This can also be stored in the environment variable UDACITY_AUTH_TOKEN.
	"""
    )
    args = parser.parse_args()

    if not args.token:
	parser.print_help()
	parser.exit()

    request_reviews(args.token)

