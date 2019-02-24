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


def format_filepath(folder, filename):
    if folder[-1] != "/":
        folder += "/"

    if filename[-4:] != ".csv":
        filename += ".csv"

    return folder + filename


def find_adds_deletes(filepath, data, data_html, colnames):
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


def print_table(table, company_name, message_start):
    print("\n" + message_start + (" for " + company_name) * (company_name != "") + ":\n")
    print(table)
    print("\n")


def create_text_table(data, colnames):
    return tabulate(data, headers=colnames)


def create_html_table(data, colnames):
    return tabulate(data, headers=colnames, tablefmt='html')


def build_message(adds_table, adds_table_html, deletes_table, deletes_table_html,
                  company_name, email_adds, email_deletes):
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

# https://developers.google.com/gmail/api/quickstart/python
# https://developers.google.com/gmail/api/guides/sending
def establish_service():
    """
    Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
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
    Create a message for an email

    Args:
    sender: Email address of the sender
    to: Email address of the receiver
    subject: The subject of the email message
    message_text: The text of the email message
    message_html: The HTML for the email message if sending an HTML email

    Returns:
    An object containing a base64url encoded email object.
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

    :param service: Authorized Gmail API service instance.
    :param user_id: User's email address. The special value "me" can be used to indicate the authenticated user.
    :param message: Message to be sent.
    :return:
    """

    try:
        message = (service.users().messages().send(userId=user_id, body=message)
                   .execute())
        if verbose:
            print('Message Id: %s' % message['id'])
        return message
    except HTTPError as error:
        print('An error occurred: %s' % error)

