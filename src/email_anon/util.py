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
import logging

HOST = 'cs-imap-x.stanford.edu' #MAIL Server hostname
HOST2 = 'cs.stanford.edu'
USERNAME = 'stats60' #Mailbox username
PASSWORD = 'stats60!' #Mailbox password
HEAD_TA = 'ljanson@stanford.edu'
alias1 = 'roboTA@cs.stanford.edu'
alias2 = 'stats60TA@cs.stanford.edu' #stats60TA@cs.stanford.edu
ssl = False

logger = None

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

    if len(unread_msg_nums)==0: 
      logInfo('No unread emails!')
    # print 'Messages:[ %d ]'%select_info['EXISTS']
    unread_msg_nums = response[0].split()
    da = []
    for e_id in unread_msg_nums:
        _, response = server1.fetch(e_id,'(RFC822)')
        da.append(response[0][1])
    return unread_msg_nums,da

def run_script(unread_msg_nums,response,server1,server2):
        student_db,student_group,student_ta = parse_student_info()
        setupLogging(loggingLevel, logFile)

        #Loop through message ID, parse the messages and extract the required info
        for data in response:
                msgStringParsed = email.message_from_string(data)
                sender =  msgStringParsed['From'].split('<')[1][:-1]

                ## if email received from student
                #print sender
                if sender != HEAD_TA:
                    if sender not in student_db:
                        logErr('Student not found in database!: %s' % sender)
                        continue
                    logInfo('Msg from student: %s to %s' % (sender, get_ta_email_from_student_email_addr(sender))
                    msg = MIMEMultipart()
                    msg['From'] = 'stats60@cs.stanford.edu'
                    msg['To'] = 'stats60TA@cs.stanford.edu'
                    msg['Subject'] = get_sid_from_student_email(sender)+'##'+ msgStringParsed['Subject']
                    body = get_body(msgStringParsed)
                    msg.attach(MIMEText(body, 'plain'))
                    server2.sendmail(sender, [HEAD_TA], msg.as_string())
                    ### Send this email

                # if email received from HEAD-TA
                else:
                    # Subject should look like this:
                    #    30#R#My Question:
                    # 30 is the id of the student who asked the question.
                    # R is head TA's guess on whether msg body is robot (R)
                    # or human (H).

                    # Get array [<sid>, <guess>, <subjectTxt>]
                    split_subject = msgStringParsed['Subject'].split('##')[0]
                    try: 
                        student_id = int(split_subject[0])
                    except ValueError:
                        # Could not find the expected sid:
                        admin_msg_to_ta('******', body)
                                       
                    charList = [i for i in split_subject.split() if i.isdigit()]
                    student_id = int(''.join(charList))
                    body = get_body(msgStringParsed)

                    # Did head TA remember to guess who msg is from?
                    try:
                        ta_guess = split_subject[1]
                        
                    except IndexError:
                        # TA forgot to guess:
                        admin_msg_to_ta('forgot to guess', body)
                        continue

                    msg = MIMEMultipart()

                    if student_id not in student_db.values(): 
                        logErr('Invalid student id: %s' % student_id)
                        continue

                    student_email =  get_student_email_addr_from_sid(student_id)

                    # FROM is changed to robota or stats60ta corresponding to the email id that student sent to
                    msg['From'] = student_ta[int(student_group[student_email])]  
                    msg['Subject'] = msgStringParsed['Subject'].split('##')[1]
                    msg['To'] = ''
                    msg.attach(MIMEText(body, 'plain'))
                    logInfo('%s replying to: %s' % (msg['From'], student_email)

                    server2.sendmail(sender, student_email, msg.as_string())
                    ## Send this email
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

    student_ta = {1:alias1,2:alias1,3:alias2,4:alias2}
    return student_db,student_group,student_ta

def setupLogging(logFile):
    '''
    Set up the standard Python logger.
    @param logFile: file to log to
    @type logFile: string
    '''
    # Set up logging:
    logger = logging.getLogger(os.path.basename(__file__))

    # Create file handler if requested:
    if logFile is not None:
        handler = logging.FileHandler(logFile)
        print('Logging will go to %s' % logFile)
    else:
        # Create console handler:
        handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter("%(name)s: %(asctime)s;%(levelname)s: %(message)s")
    handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def logDebug(msg):
    logger.debug(msg)

def logWarn(msg):
    logger.warn(msg)

def logInfo(msg):
    logger.info(msg)

def logErr(msg):
    logger.error(msg)
