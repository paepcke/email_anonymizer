import email
from imapclient import IMAPClient
import smtplib
import csv
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
import imaplib
import sched, time
import threading

HOST = 'cs-imap-x.stanford.edu' #MAIL Server hostname
HOST2 = 'cs.stanford.edu'
USERNAME = 'stats60' #Mailbox username
PASSWORD = 'stats60!' #Mailbox password
#HEAD_TA =  "aashna94@stanford.edu"
HEAD_TA = 'ljanson@stanford.edu'
alias1 = 'robota@cs.stanford.edu'
alias2 = 'stats60ta@cs.stanford.edu' #stats60TA@cs.stanford.edu
ssl = False

def setup_servers():
    server = imaplib.IMAP4_SSL(HOST, 993)
    server2 = smtplib.SMTP(HOST2,587)
    server2.starttls()
    server.login(USERNAME, PASSWORD)
    server2.login(USERNAME, PASSWORD)
    return server,server2


def get_inbox(server1,server2):
    select_info = server1.select('INBOX')
    status, response = server1.search(None, 'UnSeen')
    unread_msg_nums = response[0].split()

    if len(unread_msg_nums)==0: print 'No unread emails!'
    # print 'Messages:[ %d ]'%select_info['EXISTS']
    unread_msg_nums = response[0].split()
    da = []
    for e_id in unread_msg_nums:
        _, response = server1.fetch(e_id,'(RFC822)')
        da.append(response[0][1])
    return unread_msg_nums,da

def run_script(unread_msg_nums,response,server1,server2):
        student_db,student_group,student_ta = parse_student_info()
        #Loop through message ID, parse the messages and extract the required info
        for data in response:
                msgStringParsed = email.message_from_string(data)
                sender =  msgStringParsed['From'].split('<')[1][:-1]

                ## if email received from student
                #print sender
                if sender != HEAD_TA:
                    if sender not in student_db:
                        print 'Student not found in database!:',sender
                        return 0
                    print 'Student:',sender
                    msg = MIMEMultipart()
                    msg['From'] = 'stats60ta@cs.stanford.edu'
                    msg['To'] = 'stats60ta@cs.stanford.edu'
                    msg['Subject'] = str(student_db[sender])+'##'+ msgStringParsed['Subject']
                    body = get_body(msgStringParsed)
                    msg.attach(MIMEText(body, 'plain'))
                    server2.sendmail(sender, [HEAD_TA], msg.as_string())
                    ### Send this email

                # if email received from HEAD-TA
                else:
                    
                    containsId= msgStringParsed['Subject'].split('##')[0]
                    charList = [i for i in containsId.split() if i.isdigit()]
                    student_id = int(''.join(charList))
                    msg = MIMEMultipart()

                    if student_id not in student_db.values(): 
                        print 'Invalid student id:',student_id
                        return 0

                    student_email =  student_db.keys()[student_db.values().index(student_id)]
                    print 'TA replies to:',student_email

                    msg['From'] = student_ta[int(student_group[student_email])]  # from changed to robota or stats60ta corresponding to the email id that student sent to
                    msg['Subject'] = msgStringParsed['Subject'].split('##')[1]
                    msg['To'] = ''
                    body = get_body(msgStringParsed)
                    msg.attach(MIMEText(body, 'plain'))
                    server2.sendmail(sender, student_email, msg.as_string())
                    ## Send this email
        return 1
def get_body(email_msg):
    if email_msg.is_multipart():
        # print email_msg.get_payload(0)
        # return email_msg.get_payload(0)
        for payload in email_msg.get_payload():
            #print payload.get_payload()
            if payload.get_content_maintype() == 'text':
                return payload.get_payload()
    else: return email_msg.get_payload()

def parse_student_info():
    with open('official_randomization.csv', mode='r') as infile:
        reader = csv.reader(infile)
        student_group = {}
        for rows in reader:
            student_group[str(rows[1]).strip()] = rows[2]

        #student_group = {str(rows[1]).strip():int(rows[2])for rows in reader}

    student_db = {}  ## key: student_email, val: unique id
    i=0
    for email in student_group:
        student_db[str(email).strip()] = i
        i+=1

    student_ta = {1:alias1,2:alias1,3:alias2,4:alias2}
    return student_db,student_group,student_ta

