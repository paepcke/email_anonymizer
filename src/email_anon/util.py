
import email
import os
from imapclient import IMAPClient
import smtplib
import csv
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.parser import HeaderParser
import imaplib
import sched, time
import threading
import logging

HOST = 'cs-imap-x.stanford.edu' #MAIL Server hostname
HOST2 = 'cs.stanford.edu'
USERNAME = 'stats60' #Mailbox username
PASSWORD = 'stats60!' #Mailbox password
HEAD_TA = 'paepcke@cs.stanford.edu' #'ljanson@stanford.edu'
HEAD_TA_NAME = 'Lucas'
TA_SIG = 'Best, Lucas'
ROBO_TA_SIG = 'Greetings, RoboTA.'
robo_ta_alias = 'roboTA@cs.stanford.edu'
stats60_ta_alias = 'stats60TA@cs.stanford.edu' #stats60TA@cs.stanford.edu
ssl = False

header_parser = HeaderParser()

logger = None

def setup_servers():
    server = imaplib.IMAP4_SSL(HOST, 993)
    server2 = smtplib.SMTP(HOST2,587)
    server2.starttls()
    server.login(USERNAME, PASSWORD)
    server2.login(USERNAME, PASSWORD)    
    return server,server2


def get_inbox(server1, server2, doLog):
    select_info = server1.select('INBOX')
    status, response = server1.search(None, 'UnSeen')
    unread_msg_nums = response[0].split()

    if len(unread_msg_nums)==0: 
        if doLog:
            logInfo('No unread emails!')
        return([],[])
            
    if doLog:
        logInfo('Retrieving %s msgs from server.' % len(unread_msg_nums))

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
            try:
                msgStringParsed = email.message_from_string(data)
                sender =  msgStringParsed['From'].split('<')[1][:-1]

                ## Email received from student?
                if sender != HEAD_TA:
                    # Yes, from student:
                    if sender not in student_db:
                        logErr('Student not found in database!: %s' % sender)
                        continue
                    logInfo('Msg from student: %s to %s' % (sender, get_ta_email_from_student_email_addr(sender)))
                    msg = MIMEMultipart()
                    msg['From'] = 'stats60@cs.stanford.edu'
                    msg['To'] = 'stats60TA@cs.stanford.edu'
                    # Stick student ID into msg header:
                    msg['x-student-id'] = get_sid_from_student_email(sender)
                    msg['Subject'] = msgStringParsed['Subject']
                    body = get_body(msgStringParsed)
                    msg.attach(MIMEText(body, 'plain'))
                    ### Send this email:
                    server2.sendmail(sender, [HEAD_TA], msg.as_string())


                # Email received from HEAD-TA (a reply):
                else:

                    body = get_body(msgStringParsed)

                    # Subject should look like this:
                    #    R#My Question:
                    # Where 'R' is head TA's guess on whether msg body is robot (R)
                    # or human (H).

                    # Get array [<guess>, <subjectTxt>]

                    split_subject = msgStringParsed['Subject'].split('##')
                    if len(split_subject) != 2 or len(split_subject[0]) != 1:
                        # Could not find the expected guess:
                        admin_msg_to_ta('noGuess', body, sender=HEAD_TA)
                        continue
                                       
                    # Guess is present as single char, but is it either R or H?
                    ta_guess = split_subject[0]
                    if not (ta_guess in ['R', 'H']):
                        admin_msg_to_ta('badGuessChar', body)

                    
                    # Did TA accidentally sign his/her name?
                    if body.find(HEAD_TA_NAME) > -1:
                        admin_msg_to_ta('lucasFound', body)
                        continue

                    msg = MIMEMultipart()

                    msgDict = header_parser.parsestr(msg)

                    # Recover student id from x-student-id header field:
                    student_id = msgDict['x-student-id']

                    if student_id not in student_db.values(): 
                        logErr('Invalid student id: %s' % student_id)
                        continue

                    student_email_addr =  get_student_email_addr_from_sid(student_id)

                    # FROM is changed to robota or stats60ta corresponding to the email id that student sent to
                    from_addr = get_ta_email_from_student_email_addr(student_email_addr)

                    # Sign the return:
                    if from_addr == robo_ta_alias:
                        body += '\n\n%s' % ROBO_TA_SIG
                    else:
                        body += '\n\n%s' % TA_SIG

                    msg['From'] = from_addr
                    msg['Subject'] = split_subject[1]
                    msg['To'] = ''
                    msg.attach(MIMEText(body, 'plain'))
                    logInfo('%s replying to: %s' % (msg['From'], student_email_addr))

                    server2.sendmail(sender, student_email_addr, msg.as_string())
                    ## Send this email
            except Exception as e:
                    logErr('This error in runScript() loop: %s' % `e`)
                    #**********continue
                    raise
        return 1

def get_student_email_addr_from_sid(student_id):
    return student_db.keys()[student_db.values().index(student_id)]                    

def get_sid_from_student_email(email_addr):
    return str(student_db[email_addr])

def get_ta_email_addr_from_sid(group_num):
    return student_ta[group_num]

def get_group_num_from_email_addr(email):
    return student_db[str(email).strip()]

def get_ta_email_from_student_email_addr(email):
    return get_ta_email_addr_from_sid(get_group_num_from_email_addr(email))

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

    student_ta = {1:robo_ta_alias,
                  2:robo_ta_alias,
                  3:stats60_ta_alias,
                  4:stats60_ta_alias}
    return student_db,student_group,student_ta

def admin_msg_to_ta(errorStr, body, sender=''):

    msg = MIMEMultipart()
    msg['From'] = 'stats60@cs.stanford.edu'
    msg['To'] = 'stats60TA@cs.stanford.edu'
    # Stick student ID into msg header:
    msg['x-student-id'] = get_sid_from_student_email(sender)
    msg['Subject'] = 'You Screwed Up, Dude'
    body += 'Problem: %s\n' % errorStr
    msg.attach(MIMEText(body, 'plain'))
    server2.sendmail(sender, [HEAD_TA], msg.as_string())
        
def setupLogging(loggingLevel, logFile):
    '''
    Set up the standard Python logger.
    @param logFile: file to log to
    @type logFile: string
    '''
    # Set up logging:
    this_logger = logging.getLogger(os.path.basename(__file__))

    # Create file handler if requested:
    if logFile is not None:
        handler = logging.FileHandler(logFile)
        print('Logging will go to %s' % logFile)
    else:
        # Create console handler:
        handler = logging.StreamHandler()
    handler.setLevel(loggingLevel)
    # Create formatter
    formatter = logging.Formatter("%(name)s: %(asctime)s;%(levelname)s: %(message)s")
    handler.setFormatter(formatter)

    # Add the handler to the logger
    this_logger.addHandler(handler)
    this_logger.setLevel(loggingLevel)

    return this_logger

def logDebug(msg):
    logger.debug(msg)

def logWarn(msg):
    logger.warn(msg)

def logInfo(msg):
    logger.info(msg)

def logErr(msg):
    logger.error(msg)

logger = setupLogging(logging.INFO, 'roboTa.log')


# import sys
# (server1, server2) = setup_servers()
# (unread_msg_num_arr, unread_msg_arr) = get_inbox(server1,server2)
# print('Start msgs...')
# for msg in unread_msg_arr:
#     print msg
#     #header_data = msg[1][0][1]
#     msgDict = header_parser.parsestr(msg)
#     print('Keys: %s' % msgDict.keys())
#     print('Vals: %s'  % msgDict.values())
         
#     print('SID: %s' % msgDict['x-student-id'])
# print ("end of msgs")
