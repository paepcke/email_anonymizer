import email
from imapclient import IMAPClient
import smtplib
import csv
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

HOST = 'cs-imap-x.stanford.edu' #MAIL Server hostname
HOST2 = 'cs.stanford.edu'
USERNAME = 'stats60' #Mailbox username
PASSWORD = 'stats60!' #Mailbox password
HEAD_TA =  "aashna94@stanford.edu"#'ljanson@stanford.edu'
alias1 = 'robota@cs.stanford.edu'
alias2 = 'stats60ta@cs.stanford.edu' #stats60TA@cs.stanford.edu
ssl = False

def setup_servers():
    server = IMAPClient(HOST, use_uid=True, ssl=ssl)
    server2 = smtplib.SMTP(HOST2,587)
    server2.starttls()
    server.login(USERNAME, PASSWORD)
    server2.login(USERNAME, PASSWORD)
    return server,server2

def get_inbox():
    server1,server2 = setup_servers()
    select_info = server.select_folder('INBOX')
    messages = server.search(['ALL'])
    # print 'Messages:[ %d ]'%select_info['EXISTS']
    response = server.fetch(messages, ['RFC822'])
    return response

def get_body(email_msg):
    if email_msg.is_multipart():
        for payload in email_msg.get_payload():
            if payload.get_content_maintype() == 'text':
                return payload.get_payload()
    else: return email_msg.get_payload()

def parse_student_info():
    student_db = {}  ## key: student_email, val: unique id
    f = open('statsClassEmails.txt')
    i=0
    for line in f:
        student_db[str(line.strip())]=i
        i+=1

    with open('official_randomization.csv', mode='r') as infile:
        reader = csv.reader(infile)
        student_group = {rows[1]:rows[2] for rows in reader}
    student_ta = {1:alias1,2:alias1,3:alias2,4:alias2}
    return student_db,student_group,student_ta

