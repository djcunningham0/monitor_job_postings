from bs4 import BeautifulSoup as bs
import requests
from tabulate import tabulate
import csv
from datetime import datetime
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import base64
from urllib.error import HTTPError


def get_soup(url, headers=None, verbose=True):
    """
    Get the HTML for a given URL using the BeautifulSoup library.

    :return: a BeautifulSoup object
    """
    result = requests.get(url, headers=headers)
    if result.status_code != 200:
        if verbose:
            print("Failed to connect to {} with error code: {}".format(url, result.status_code))
        return None
    else:
        soup = bs(result.content, 'html5lib')
        return soup


def format_csv_filepath(filepath):
    """
    Makes sure the file name ends in '.csv'

    :param filepath: full file path for CSV file (string)
    :return: full file path ending in '.csv'
    """
    if filepath[-4:] != ".csv":
        filepath += ".csv"

    return filepath


def find_adds_deletes(filepath, data, data_html, colnames):
    """
    Compare the scraped data with the last recorded data in a CSV file and check for differences to see if any jobs
    were added or deleted.

    :param filepath: file path of the CSV file (string)
    :param data: scraped data with job information (list)
    :param data_html: scraped data with job information to be displayed in HTML email (e.g., including hyperlinks)
    :param colnames: names of the fields in 'data' to be used as column names in the email (list of strings)
    :return: three lists of jobs data -- added jobs, added jobs with HTML formatting, and deleted jobs
    """
    with open(filepath, 'r') as csvfile:
        reader = csv.reader(csvfile)
        csvrows = [row[0:len(colnames)] for row in reader]  # ignore the timestamp (last column)
        csvrows = csvrows[1:]  # first row is header

        # if job is on the website and not in the CSV, it was added
        adds = [item for item in data if item not in csvrows]
        adds_html = [data_html[i] for i, item in enumerate(data_html) if data[i] not in csvrows]

        # if job is in the CSV and not on the website, it was deleted
        deletes = [row for row in csvrows if row not in data]

    csvfile.close()

    return adds, adds_html, deletes


def create_text_table(data, colnames):
    """
    Use the tabulate library to create a plain-text table of job data.

    :param data: job data
    :param colnames: names of fields in job data to be used as column names
    :return: a plain-text table
    """
    return tabulate(data, headers=colnames)


def create_html_table(data, colnames):
    """
    Use the tabulate library to create an HTML table of job data.

    :param data: job data
    :param colnames: names of fields in job data to be used as column names
    :return: an HTML table
    """
    return tabulate(data, headers=colnames, tablefmt='html')


def print_table(table, company_name, message_start=None):
    """
    Print job data to the console.

    :param table: table of job data created using create_text_table or create_html_table
    :param company_name: name of the company
    :param message_start: message to display before printing the table (optional)
    """
    if message_start is not None and message_start != "":
        print("\n" + message_start + (" for " + company_name) * (company_name != "") + ":\n")

    print(table)
    print("\n")


def build_message(adds_table, adds_table_html, deletes_table, deletes_table_html,
                  company_name, email_adds=True, email_deletes=True):
    """
    Build the email message including added and removed jobs.

    :param adds_table: table of added jobs created from create_text_table
    :param adds_table_html: table of added jobs created from create_html_table
    :param deletes_table: table of deleted jobs created from create_text_table
    :param deletes_table_html: table of deleted jobs created from create_html_table
    :param company_name: name of company
    :param email_adds: True to include added jobs in the email
    :param email_deletes: True to include deleted jobs in the email
    :return: a plain-text email message and an HTML email message
    """
    text_msg = ""
    html_msg = ""

    if email_adds:
        text_msg += "\nNew jobs posted" + (" for " + company_name) * (company_name != "") + ":\n\n"
        text_msg += "{adds_table}\n\n"
        html_msg += "\n<p>New jobs posted" + (" for " + company_name) * (company_name != "") + ":</p>\n"
        html_msg += "{adds_html_table}\n"

    if email_deletes:
        text_msg += "\nJobs removed" + (" for " + company_name) * (company_name != "") + ":\n\n"
        text_msg += "{deletes_table}\n\n"
        html_msg += "\n<p>Jobs removed" + (" for " + company_name) * (company_name != "") + ":</p>\n"
        html_msg += "{deletes_html_table}\n"

    html_msg = "\n<html><body>" + html_msg + "</body></html>\n"

    html_msg = html_msg.format(adds_html_table=adds_table_html,
                               deletes_html_table=deletes_table_html)

    text_msg = text_msg.format(adds_table=adds_table,
                               deletes_table=deletes_table)

    # add horizontal padding to table to make it look nicer
    html_msg = html_msg.replace('<html>',
                                '<html>\n<head>\n<style>\ntable {\n\tborder-spacing: 10px 0;\n}\n</style>\n</head>\n')

    return text_msg, html_msg


def write_csv(filepath, data, colnames):
    """
    Write the jobs data to a CSV file which will be used to check for changes.

    :param filepath: full filepath for CSV file
    :param data: scraped jobs data
    :param colnames: column names for the file
    """
    # create the directory if it doesn't exist
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'w') as csvfile:
        writer = csv.writer(csvfile)

        headers = colnames + ["last checked"]
        writer.writerow(headers)

        now = datetime.now()

        for item in data:
            writer.writerow(item + [now])

        csvfile.close()


### Begin Gmail API utilities ###

# A few helpful links for setting up the API:
# https://developers.google.com/gmail/api/quickstart/python
# https://developers.google.com/gmail/api/guides/sending

def establish_service():
    """
    Authorizes and establishes the Gmail service using the API.

    :return: authorized Gmail service instance
    """
    # If modifying these scopes, delete the file token.pickle.
    SCOPES = ['https://www.googleapis.com/auth/gmail.send']

    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)

    return service


def create_message(sender, to, subject, message_text, message_html=None):
    """
    Create a message for an email.

    :param sender: email address of the sender
    :param to: email address of the recipient
    :param subject: subject of the email
    :param message_text: plain-text version of the email body
    :param message_html: HTML version of the email body
    :return: an object containing a base64url encoded email object
    """
    if message_html is not None:
        message = MIMEMultipart('alternative', None, [MIMEText(message_text), MIMEText(message_html, 'html')])
    else:
        message = MIMEText(message_text)

    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}


def send_message(service, user_id, message, verbose=False):
    """
    Send an email message.

    :param service: authorized Gmail API service instance.
    :param user_id: user's email address -- the special value "me" can be used to indicate the authenticated user.
    :param message: message to be sent
    """

    try:
        message = (service.users().messages().send(userId=user_id, body=message)
                   .execute())
        if verbose:
            print('Message Id: %s' % message['id'])
        return message
    except HTTPError as error:
        print('An error occurred: %s' % error)

