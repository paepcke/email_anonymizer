
import email
import os
import re
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

GUESS_RECORD_FILE = 'taGuessRecord.csv'

robo_ta_alias = 'roboTA@cs.stanford.edu'
stats60_ta_alias = 'stats60TA@cs.stanford.edu' #stats60TA@cs.stanford.edu
admin_alias = 'paepcke@cs.stanford.edu'

ssl = False


class EmailChecker(object):


    def __init__(self):

        self.header_parser = HeaderParser()

        self.setupLogging(logging.INFO, 'roboTa.log')

        self.serverReceiving = imaplib.IMAP4_SSL(HOST, 993)

        self.serverSending = smtplib.SMTP(HOST2,587)
        self.serverSending.starttls()

        self.serverReceiving.login(USERNAME, PASSWORD)
        self.serverSending.login(USERNAME, PASSWORD)

        # Regex for start of line being H, R, human, Human, Robot, robot, followed by \n or \r:
        self.guess_pattern = re.compile(r'(H)[\n\r]|(R)[\n\r]|([hH]uman)[\n\r]|([rR]obot)[\n\r]')


    def get_inbox(self, doLogNumMsgs):
        select_info = self.serverReceiving.select('INBOX')
        status, response = self.serverReceiving.search(None, 'UnSeen')
        unread_msg_nums = response[0].split()

        if len(unread_msg_nums)==0: 
            if doLogNumMsgs:
                self.logInfo('No unread emails!')
            return([],[])
                
        self.logInfo('Retrieving %s msg(s) from server.' % len(unread_msg_nums))

        # print 'Messages:[ %d ]'%select_info['EXISTS']
        da = []
        for e_id in unread_msg_nums:
            _, response = self.serverReceiving.fetch(e_id,'(RFC822)')
            da.append(response[0][1])
        return unread_msg_nums, da

    def markSeen(self, unread_msgs):
        for eid in unread_msgs:
            self.serverReceiving.store(eid, '+FLAGS', '\Seen')


    def run_script (self, unread_msg_nums, response):

            self.parse_student_info()

            #***************
            #print('Response: %s' % str(response))
            #***************

            #Loop through message ID, parse the messages and extract the required info
            for data in response:
                try:
                    msgStringParsed = email.message_from_string(data)

                    #*****************
                    #print('msgStringParsed: %s' % str(msgStringParsed))
                    #*****************

                    sender =  msgStringParsed['From'].split('<')[1][:-1]
                    dest   =  msgStringParsed['To']

                    #****************
                    #print('Dest: %s' % dest)
                    #****************

                    ## Email received from student?
                    if sender != HEAD_TA:
                        # Yes, from student:
                        if sender not in self.student_db:
                            self.logErr('Student not found in database!: %s' % sender)
                            continue
                        self.logInfo('Msg from student: %s to %s' % (sender, dest))
                        msg = MIMEMultipart()
                        msg['From'] = 'stats60@cs.stanford.edu'
                        msg['To'] = 'stats60TA@cs.stanford.edu'

                        # Stick destination of student's msg into msg header:
                        msg['x-student-dest'] = str(dest)
                        # Same for student's return email:
                        msg['x-student-email'] = str(sender)

                        #**************
                        #print('Sender: %s. SID: %s' % (sender, self.get_sid_from_student_email(sender)))
                        #**************

                        msg['Subject'] = msgStringParsed['Subject']
                        body = self.get_body(msgStringParsed)
                        msg.attach(MIMEText(body, 'plain'))
                        ### Send this email:
                        self.serverSending.sendmail(sender, [HEAD_TA], msg.as_string())


                    # Email received from HEAD-TA (a reply):
                    else:

                        body    = self.get_body(msgStringParsed)
                        subject = msgStringParsed['Subject']
                        date    = msgStringParsed['Date']
                        msg_id  = msgStringParsed['Message-ID']

                        #*******************
                        #print("Body: %s" % body)
                        #*******************

                        # First line of body is to be a line that
                        # is empty except for the human/robot guess:

                        match = self.guess_pattern.match(body) 
                        if match is None:
                            # Could not find the expected guess:
                            new_body = 'NO H or R IN FIRST LINE!\n' + self.msg_subj_plus_body(date,subject,body)
                            self.admin_msg_to_ta('noGuess', new_body)
                            continue
                        ta_guess = match.group().strip()
                            
                                           
                        # Did TA accidentally sign his/her name?
                        if body.find(HEAD_TA_NAME) > -1:
                            new_body = "Found '%s' in message." % HEAD_TA_NAME + self.msg_subj_plus_body(date,subject,body)
                            self.admin_msg_to_ta('lucasFound', body)
                            continue

                        # Recover dest of original address from x-student-dest header field:
                        orig_dest = msgStringParsed['x-student-dest']

                        # Same for student's return email:
                        student_email_addr = msgStringParsed['x-student-email']

                        #*************
                        print('Recovered orig_dest: %s' % orig_dest)
                        print('Recovered stud_email: %s' % student_email_addr)
                        #*************

                        # FROM is changed to robota or stats60ta corresponding to the 
                        # address that the student sent to.
                        
                        # Record the original destination as the truth the TA was to guess:
                        self.record_ta_guess(date, msg_id, orig_dest, guess=ta_guess)

                        # Sign the return:
                        if orig_dest == robo_ta_alias:
                            body += '\n\n%s' % ROBO_TA_SIG
                        else:
                            body += '\n\n%s' % TA_SIG

                        msg = MIMEMultipart()

                        msg['From'] = orig_dest
                        msg['Subject'] = subject
                        msg['To'] = ''
                        msg.attach(MIMEText(body, 'plain'))
                        self.logInfo('%s replying to: %s' % (msg['From'], student_email_addr))

                        self.serverSending.sendmail(sender, [student_email_addr], msg.as_string())
                        ## Send this email
                except Exception as e:
                        self.logErr('This error in runScript() loop: %s' % `e`)
                        #**********continue
                        raise
            return 1

    def record_ta_guess(self, date, msg_id, true_origin, guess='origin'):
        with open(GUESS_RECORD_FILE, 'a') as fd:
            fd.write('%s,%s,%s,%s\n' % (date, msg_id, true_origin, guess))

    def msg_subj_plus_body(self, date, subject, body):
        return 'On %s: %s\n%s' % (date,subject,body)

    def get_student_email_addr_from_sid(self, student_id):
        return self.student_db.keys()[self.student_db.values().index(student_id)]                    

    def get_sid_from_student_email(self, email_addr):
        try:
            return str(self.student_db[email_addr])
        except KeyError:
            return None

    def get_ta_email_addr_from_group_num(self, group_num):
        return self.student_ta[group_num]

    def get_group_num_from_email_addr(self, email):
        return self.student_group[email]

    def get_ta_email_from_student_email_addr(self, email):
        return self.get_ta_email_addr_from_group_num(self.get_group_num_from_email_addr(email))

    def get_body(self, email_msg):
        if email_msg.is_multipart():
            # print email_msg.get_payload(0)
            # return email_msg.get_payload(0)
            for payload in email_msg.get_payload():
                #print payload.get_payload()
                if payload.get_content_maintype() == 'text':
                    return payload.get_payload()
        else: return email_msg.get_payload()

    def parse_student_info(self):
        with open('official_randomization.csv', mode='r') as infile:
            reader = csv.reader(infile)
            self.student_group = {}
            for rows in reader:
                self.student_group[str(rows[1]).strip()] = rows[2]

            #self.student_group = {str(rows[1]).strip():int(rows[2])for rows in reader}

        self.student_db = {}  ## key: student_email, val: unique id
        i=0
        for email in self.student_group:
            self.student_db[str(email).strip()] = i
            i+=1

        self.student_ta = {'1':robo_ta_alias,
                           '2':robo_ta_alias,
                           '3':stats60_ta_alias,
                           '4':stats60_ta_alias}

    def admin_msg_to_ta(self, errorStr, body):

        sender = admin_alias
        msg = MIMEMultipart()
        msg['From'] = admin_alias
        msg['To'] = HEAD_TA
        # Stick student ID into msg header:
        msg['x-student-id'] = self.get_sid_from_student_email(sender)
        msg['Subject'] = 'You Screwed Up, Dude'
        body += 'Problem: %s\n' % errorStr
        msg.attach(MIMEText(body, 'plain'))
        self.serverSending.sendmail(sender, [HEAD_TA], msg.as_string())
            
    def setupLogging(self, loggingLevel, logFile):
        '''
        Set up the standard Python logger.
        @param logFile: file to log to
        @type logFile: string
        '''
        # Set up logging:
        self.logger = logging.getLogger(os.path.basename(__file__))

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
        self.logger.addHandler(handler)
        self.logger.setLevel(loggingLevel)

    def logDebug(self, msg):
        self.logger.debug(msg)

    def logWarn(self, msg):
        self.logger.warn(msg)

    def logInfo(self, msg):
        self.logger.info(msg)

    def logErr(self, msg):
        self.logger.error(msg)


# import sys
# (serverReceiving, serverSending) = setup_servers()
# (unread_msg_num_arr, unread_msg_arr) = get_inbox(serverReceiving,serverSending)
# print('Start msgs...')
# for msg in unread_msg_arr:
#     print msg
#     #header_data = msg[1][0][1]
#     msgDict = header_parser.parsestr(msg)
#     print('Keys: %s' % msgDict.keys())
#     print('Vals: %s'  % msgDict.values())
         
#     print('SID: %s' % msgDict['x-student-id'])
# print ("end of msgs")
