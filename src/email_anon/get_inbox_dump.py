#!/usr/bin/env python

import csv
import email
import imaplib
import os
import socket
import sys


# The imap box:
HOST = 'cs-imap-x.stanford.edu' #MAIL Server hostname
HOST2 = 'cs.stanford.edu'
USERNAME = 'stats60' #Mailbox username
MAILBOX_EMAIL = 'stats60@cs.stanford.edu'
IMAP_PWD_FILE = 'imap_password.txt'          # File containing imap password in ~/.ssh

def get_password_from_file():
    # Get mailbox password from ~/.ssh/imap_pwd.txt
    try:
        with open(os.path.join(os.getenv('HOME'), '.ssh', IMAP_PWD_FILE)) as fd:
            return fd.read().strip()
    except IOError:
        print('Cannot read pwd from ~/%s. Nothing sent.' % IMAP_PWD_FILE)
        sys.exit(1)

PASSWORD = get_password_from_file()
OUTPUT_DUMP_FILE = 'email_dump.csv'
dump = open(OUTPUT_DUMP_FILE, 'wb')
wr = csv.writer(dump, quoting=csv.QUOTE_ALL)
wr.writerow(['From','To','Date','Subject','Body'])
print('Creating server instance...')
try:
    server = imaplib.IMAP4_SSL(HOST, 993)
except socket.error:
    print('Could not connect to imap server; make sure you are inside Stanford or on VPN.')
    sys.exit(1)
print('Done creating server instance...')
print('Loging into IMAP server...')
server.login(USERNAME, PASSWORD)
print('Done loging into IMAP server...')

def get_body(email_msg):
        '''
        Dig body out of a raw email string.
        
        :param email_msg: raw email
        :type email_msg: string
        :return just the message body
        '''
        text = ""
        if email_msg.is_multipart():
            html = None
            for payload in email_msg.get_payload():
                if payload.get_content_charset() is None:
                # We cannot know the character set, so return decoded "something"
                    text = payload.get_payload(decode=True)
                    if '________________________________' in text: text = text.split('________________________________')[0]
                    continue
                charset = payload.get_content_charset()
                if payload.get_content_maintype() == 'text':
                    text = unicode(payload.get_payload(decode=True), str(charset), "ignore").encode('utf8', 'replace')
                
            if text is not None:
                if '________________________________' in text: text = text.split('________________________________')[0]
                return text.strip() 

        else:
            if email_msg.get_content_charset() is not None:
                text = unicode(email_msg.get_payload(decode=True), email_msg.get_content_charset(), 'ignore').encode('utf8', 'replace')
            else: text = email_msg.get_payload(decode=True)
            if '________________________________' in text: text = text.split('________________________________')[0]
            return text.strip()

def get_body2( email_msg):
        '''
        Dig body out of a raw email string.
        
        :param email_msg: raw email
        :type email_msg: string
        :return just the message body
        '''
        
        if email_msg.is_multipart():
            # print email_msg.get_payload(0)
            # return email_msg.get_payload(0)
            for payload in email_msg.get_payload():
                #print payload.get_payload()
                if payload.get_content_maintype() == 'text':
                    return payload.get_payload()
        else: return email_msg.get_payload()
def get_inbox():
    select_info = server.select('INBOX',readonly=True)
    status, response = server.search(None, 'All')
    msg_nums = response[0].split()
    da = []
    for e_id in msg_nums:
        _, response = server.fetch(e_id,'(RFC822)')
        da.append(response[0][1])
    return da


def parse_emails(response):
    for data in response:
                msgStringParsed = email.message_from_string(data)
                frm =  msgStringParsed['From']
                if '<' in frm: frm =  msgStringParsed['From'].split('<')[1][:-1]
                to =  msgStringParsed['To'].split(' ')[0]
                subject = msgStringParsed['Subject']
                body = get_body2(msgStringParsed)
                date= msgStringParsed['Date']
                # msg = MIMEMultipart("alternative")
                # msg['From'] = frm
                # msg['Subject'] = subject
                # msg['To'] = ''
                # print MIMEText(body.encode('utf-8'), 'plain','utf-8')
                # msg.attach(MIMEText(body.encode('utf-8'), 'plain','utf-8'))
                #print msg.as_string().encode('ascii')
                wr.writerow([frm,to,date,subject,body])

print('Getting raw email structures...')
data = get_inbox()
print('Done getting raw email structures...')
print('Parsing emails...')
parse_emails(data)
print("Result in %s" % os.path.join(os.path.dirname(__file__), OUTPUT_DUMP_FILE))