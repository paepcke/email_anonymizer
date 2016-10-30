
import csv
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import imaplib
import logging
import os
import re
import smtplib

from mock.mock import self

'''
Module for relaying messages between students and robot/TA.

'''

HOST = 'cs-imap-x.stanford.edu' #MAIL Server hostname
HOST2 = 'cs.stanford.edu'
USERNAME = 'stats60' #Mailbox username
PASSWORD = 'stats60!' #Mailbox password
HEAD_TA = 'ljanson@stanford.edu'
#HEAD_TA = 'paepcke@stanford.edu'
HEAD_TA_NAME = 'Lucas'
TA_SIG = 'Best, Lucas'
ROBO_TA_SIG = 'Greetings, RoboTA.'

# Will be placed in same dir as this script:
LOG_FILE = 'roboTA.log'

# Where TA's guesses as to the origin
# of each student question's grp assignment
# are stored. Will be placed in same dir as
# this script:
GUESS_RECORD_FILE = 'taGuessRecord.csv'

robo_ta_alias = 'roboTA@cs.stanford.edu'
stats60_ta_alias = 'stats60TA@cs.stanford.edu' #stats60TA@cs.stanford.edu
admin_alias = 'paepcke@cs.stanford.edu'

ssl = False

TEST = None

destination_addrs = [robo_ta_alias.lower(), stats60_ta_alias.lower()]
                         

class EmailChecker(object):

    def __init__(self, logFile=LOG_FILE):
        
        # Path to this script:
        self.script_path = os.path.dirname(__file__)
        if not os.path.isabs(logFile):
            logFile = os.path.join(self.script_path, logFile)
        
        self.log_file = logFile
        self.setupLogging(logging.INFO, self.log_file)

        # Regex for start of line being H, R, human, Human, Robot, robot, followed by \n or \r:
        self.guess_pattern = re.compile(r'(H)[\n\r]|(R)[\n\r]|(h)[\n\r]|(r)[\n\r]|([hH]uman)[\n\r]|([rR]obot)[\n\r]')

        # Regex for removing *****SPAM***** at start of subject:
        self.starSpamPattern = re.compile(r'([^*]*)(\*\*\*\*\*SPAM\*\*\*\*\*)(.*)')

        # Regex for removing [SPAM:####] at start of subject:
        self.sharpSpamPattern = re.compile(r'([^#]*)(\[SPAM:####\])(.*)')
        
        # Regex to find 'Best, TA_SIG':
        self.ta_sig_pattern = re.compile(r'\n\n' + TA_SIG + r'$')

        # Regex to match TA greeting
        self.robo_greeting = re.compile(r'([rR]obo)[\n\r]{0,1}',flags=re.IGNORECASE)
        self.lucas_greeting = re.compile(r'([lL]ucas)[\n\r]{0,1}',flags=re.IGNORECASE)
        
        # For remembering which student sent
        # original msg to robot/human, and to
        # remember students' email address.
        # Format:  <msgID> ==> (orig_dest, student_email)
                 
        self.traffic_record = {}
        
        # Build internal database of legitimate student senders:
        self.parse_student_info()

        # Log into the IMAP server. Since we keep 
        # querying it every 15 seconds, it seems to
        # stay connected, and we only login once:

        self.login_receiving()

    def login_sending(self):
        '''
        Login into sendmail server
        '''
        self.serverSending = smtplib.SMTP(HOST2,587)
        self.serverSending.starttls()
        self.serverSending.login(USERNAME, PASSWORD)
        
    def logout_sending(self):
        self.serverSending.quit()

    def login_receiving(self):
        '''
        Log into the IMAP server.
        '''
        self.serverReceiving = imaplib.IMAP4_SSL(HOST, 993)
        self.serverReceiving.login(USERNAME, PASSWORD)

    def logout_receiving(self):
        self.serverReceiving.close()
        self.serverReceiving.logout()
        

    def get_inbox(self, doLogNumMsgs):
        '''
        Contact IMAP server, and retrieve 
        message numbers.
        
        :param doLogNumMsgs: if True, writes to log
            to show that inbox still being queried. 
            Caller thereby controls how much to clutter
            log with "No unread emails!"
        :type doLogNumMsgs: bool
        :return array of unread message numbers and header envelopes
        :rtype: [int, string]
        '''
        
        num_msgs = self.serverReceiving.select('INBOX') # @UnusedVariable
        typ, msgnums = self.serverReceiving.search(None, 'UnSeen') #@Unus @UnusedVariable
        unread_msg_nums = msgnums[0].split()

        if len(unread_msg_nums)==0: 
            if doLogNumMsgs:
                self.logInfo('No unread emails!')
            return([],[])
                
        self.logInfo('Retrieving %s msg(s) from server.' % len(unread_msg_nums))

        # print 'Messages:[ %d ]'%select_info['EXISTS']
        da = []
        for e_id in unread_msg_nums:
            _, msgnums = self.serverReceiving.fetch(e_id,'(RFC822)')
            da.append(msgnums[0][1])
        return unread_msg_nums, da

    def mark_seen(self, unread_msgs):
        '''
        Mark given messages as 'seen' on the IMAP server.
        They are not deleted theere.
        
        :param unread_msgs: message numbers as returned by get_inbox()
        :type unread_msgs: [int]
        '''
        for eid in unread_msgs:
            self.serverReceiving.store(eid, '+FLAGS', '\Seen')


    def pull_msgs (self, unread_msg_nums, response):
        '''
        Workhorse. Receives given IMAP message numbers as returned
        by get_inbox(), and an array of message strings: check whether
        msg is from student or from head ta. If from student, records
        the student's email and the message's msg-id (as found in header).
        Retains those to use when TA response arrives. 
        
        Forwards student msg to TA, adding the message's msg-id to the 
        subject line (Ugly, but only TA sees it). Note: this cookie needs
        to change each time so TA cannot begin to guess which student is 
        which group.
        
        If incoming msg is from TA, checks whether first line is one of
        h,r,H,R,human,Human,robot, or Robot. If not, sends prompt to TA
        to re-send. The info are the TA's guess whether the student is sending
        to a robot or a human.
        
        Checks whether TA accidentally signed their name. Very narrow check:
        "Best, <taName>". If signature found, sends message to TA requesting
        a re-do.
        
        Else: forwards the TA's response to the student, originating from the
        actor to which the original msg was directed: stats60TA or roboTA.
        
        :param unread_msg_nums: messages numbers as returned from get_inbox()
        :type unread_msg_nums: [int]
        :param response: array of message strings
        :type response: [string]
        :return +1/-1 to indicate success. Caller is expected to preserve non-seen
            status on IMAP server if receives -1.
        :rtype: int
        '''

        #Loop through message ID, parse the messages and extract the required info
        for data in response:
            try:
                msgStringParsed = email.message_from_string(data)

                sender =  msgStringParsed['From'].split('<')[1][:-1]
                dest   =  msgStringParsed['To']
                msg_id =  msgStringParsed['Message-ID']

                ## Email received from student?
                if sender != HEAD_TA:
                    # Yes, from student:
                    if sender not in self.student_db:
                        self.logErr('Student not found in database!: %s' % sender)
                        continue
                    self.logInfo('Msg from student: %s to %s' % (sender, dest))
                    
                    # Prepare message to send to TA:
                    
                    msg = MIMEMultipart()
                    body = self.get_body(msgStringParsed)

                    body = self.lucas_greeting.sub('TA',body)
                    body = self.robo_greeting.sub('',body)
                    subject = self.cleanSubjectOfSpamNotice(msgStringParsed['Subject'])
                    subject = self.lucas_greeting.sub('TA',body)
                    subject = self.robo_greeting.sub('',subject)
                    
                    msg.attach(MIMEText(body, 'plain'))
                    msg['From'] = 'stats60ta@cs.stanford.edu'
                    msg['To'] = 'stats60ta@cs.stanford.edu'
                    msg['Subject'] = subject + '   RouteNo:' + msg_id
                    
                    # Remember to whom student sent her msg, and her 
                    # return addr:
                    self.traffic_record[msg_id] = (sender, dest) 
                    
                    ### Send this email:
                    self.login_sending()
                    #self.serverSending.sendmail('stats60ta@cs.stanford.edu', [HEAD_TA], msg.as_string())
                    self.serverSending.sendmail(sender, [HEAD_TA], msg.as_string())

                # Email received from HEAD-TA (a reply):
                else:

                    body    = self.get_body(msgStringParsed)
                    subject = self.cleanSubjectOfSpamNotice(msgStringParsed['Subject'])
                    date    = msgStringParsed['Date']

                    # First line of body is to be a line that
                    # is empty except for the human/robot guess:

                    match = self.guess_pattern.match(body) 
                    if match is None:
                        # Could not find the expected guess:
                        new_body = 'NO H or R IN FIRST LINE!\n' + self.msg_subj_plus_body(date,subject,body)
                        self.admin_msg_to_ta('noGuess', new_body)
                        continue
                    else:
                        ta_guess = match.group().strip()
                        # Remove the guess from the body before sending
                        # on to the student:
                        body = body[len(ta_guess):]                        
                        
                    # Did TA accidentally sign his/her name?
                    if self.ta_sig_pattern.match(body) is not None:
                        new_body = "Found '%s' in message." % HEAD_TA_NAME + self.msg_subj_plus_body(date,subject,body)
                        self.admin_msg_to_ta('lucasFound', body)
                        continue

                    # Recover dest of original address from x-student-dest header field:
                    (orig_subject, orig_msg_id) = subject.split('RouteNo:')
                    (student_sender, orig_dest) = self.traffic_record.get(orig_msg_id, (None, None))
                    
                    subject = orig_subject
                    
                    if student_sender is None or orig_dest is None:
                        self.logErr("Missing msg record: %s" % orig_msg_id)
                        continue
                    else:
                        try:
                            # Done dealing with this request:
                            del self.traffic_record[orig_msg_id]
                        except:
                            pass
                     
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
                    self.logInfo('%s replying to: %s' % (msg['From'], student_sender))

                    self.login_sending()
                    # Use destination of student's original msg
                    # as sender in this sendmail call. That will either
                    # be robota@cs.stanford.edu, or statst60ta@cs.stanford.edu.
                    # In any case: this needs to be a xxx@cs.stanford.edu address!
                    # Else CS mail server silently drops the msg: 
                    self.serverSending.sendmail(orig_dest, [student_sender], msg.as_string())
                    ## Send this email
            except Exception as e:
                    self.logErr('This error in runScript() loop: %s' % `e`)
                    continue
                    raise
        return 1

    def record_ta_guess(self, date, msg_id, true_origin, guess='origin'):
        '''
        Write the TA's guess as to destination intent of student message
        to a log. Normalizes the flexible first-line guesses (r,R,human,Robot, etc.)
        to 'human' and 'robot'. 
        
        :param date: date of the original message
        :type date: string
        :param msg_id: message header msg-id
        :type msg_id: string
        :param true_origin: student's email address TO field.
        :type true_origin: string
        :param guess: the TA guess as recorded on first line of return.
        :type guess: string
        '''
        
        # true_origin is the email of the roboTA or the stats TA.
        # Normalize that into: 'robot' and 'human'
        if true_origin == stats60_ta_alias:
            true_origin = 'human'
        else:
            true_origin = 'robot'
            
        # Same for the guess: could the h, H, Human, human, R, r, Robot, or robot:
        if guess[0] in ['R','r']:
            guess = 'robot'
        else:
            guess = 'human'
        
        with open(os.path.join(self.script_path, GUESS_RECORD_FILE), 'a') as fd:
            fd.write('%s,%s,%s,%s\n' % (date, msg_id, true_origin, guess))

    def msg_subj_plus_body(self, date, subject, body):
        return 'On %s: %s\n%s' % (date,subject,body)

    def get_body(self, email_msg):
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

    def parse_student_info(self):
        '''
        Read student emails from official_randomization.csv, and
        create internal data structure to hold them.
        '''

        this_script_dir  = os.path.dirname(__file__)
        student_dir_path = os.path.join(this_script_dir, 'official_randomization.csv')
        try:
            with open(student_dir_path, mode='r') as infile:
                reader = csv.reader(infile)
                self.student_group = {}
                for rows in reader:
                    self.student_group[str(rows[1]).strip()] = rows[2]
    
                #self.student_group = {str(rows[1]).strip():int(rows[2])for rows in reader}
        except Exception as e:
            raise IOError("Could not open student email list at %s (%s)" % (student_dir_path, `e`))
        
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
        '''
        Send a msg to TA with out-of-band information.
        Ensures that TA replying does not go to students.
        
        :param errorStr: very short keyword that indicates error condition
        :type errorStr: stringt
        :param body: body of msg to send
        :type body: string
        '''

        sender = admin_alias
        msg = MIMEMultipart()
        msg['From'] = admin_alias
        msg['To'] = HEAD_TA
        # Stick student ID into msg header:
        msg['Subject'] = 'You Screwed Up, Dude: %s' % errorStr
        body += 'Problem: %s\n' % errorStr
        msg.attach(MIMEText(body, 'plain'))
        self.logErr('Lucas screwed up: %s' % errorStr)
        self.login_sending()
        self.serverSending.sendmail(sender, [HEAD_TA], msg.as_string())
        
    def cleanSubjectOfSpamNotice(self, subject):
        '''
        Given a subject line, remove *****SPAM***** and [SPAM:####]
        
        :param subject: string from which to remove the spam notices
        :type subject: string
        '''
        
        try:
            starSpamMatch = self.starSpamPattern.match(subject)
            if starSpamMatch is not None:
                noStarSpamSubj = starSpamMatch.groups()[2]
            else:
                noStarSpamSubj = subject
        
            sharpSpamMatch = self.sharpSpamPattern.match(noStarSpamSubj)
            if sharpSpamMatch is not None:
                cleanSubj = sharpSpamMatch.groups()[2]
            else:
                cleanSubj = noStarSpamSubj
        except Exception:
            cleanSubj = subject
            
        return cleanSubj.strip()

            
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
        
        self.logInfo('Start logging.')
    
    def stop_logging(self):
        logging.shutdown()

    def logDebug(self, msg):
        self.logger.debug(msg)

    def logWarn(self, msg):
        self.logger.warn(msg)

    def logInfo(self, msg):
        self.logger.info(msg)

    def logErr(self, msg):
        self.logger.error(msg)

