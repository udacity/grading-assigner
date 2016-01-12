#!/usr/bin/env python
import argparse
import itertools
import logging
import os
import requests
import time

# Script config
CERTS_URL = 'https://review-api.udacity.com/api/v1/me/certifications.json'
ASSIGN_URL = 'https://review-api.udacity.com/api/v1/projects/{pid}/submissions/assign.json'
REVIEW_URL = 'https://review.udacity.com/#!/submissions/{sid}'
REQUESTS_PER_SECOND = 1 # Please leave this alone.

logging.basicConfig(format = '|%(asctime)s| %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def request_reviews(token):
    headers = {'Authorization': token, 'Content-Length': '0'}

    logger.info("Requesting certifications...")
    certs_resp = requests.get(CERTS_URL, headers=headers)
    certs_resp.raise_for_status()

    certs = certs_resp.json()
    project_ids = [cert['project']['id'] for cert in certs if cert['status'] == 'certified']

    logger.info("Found certifications for project IDs: {}".format(str(project_ids)))
    logger.info("Polling for new submissions...")

    for pid in itertools.cycle(project_ids):
        resp = requests.post(ASSIGN_URL.format(pid = pid), headers=headers)
        if resp.status_code == 201:
            submission = resp.json()

            logger.info("")
            logger.info("=================================================")
            logger.info("You have been assigned to grade a new submission!")
            logger.info("View it here: " + REVIEW_URL.format(sid = submission['id']))
            logger.info("=================================================")
            logger.info("Continuing to poll...")

        elif resp.status_code == 404:
            logger.debug("{} returned {}: No submissions available."
                .format(resp.url, resp.status_code))
        elif resp.status_code in [400, 422]:
            logger.debug("{} returned {}: Assigned submission limit reached."
                .format(resp.url, resp.status_code))

        else:
            resp.raise_for_status()

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
    parser.add_argument('--debug', '-d', action='store_true', help='Turn on debug statements.')
    args = parser.parse_args()

    if not args.token:
	parser.print_help()
	parser.exit()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    request_reviews(args.token)

