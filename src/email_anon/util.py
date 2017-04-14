
import csv
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import imaplib
import logging
import os
import re
import smtplib
import shelve

from mock.mock import self

'''
Module for relaying messages between students and robot/TA.

'''

# The imap box:
HOST = 'cs-imap-x.stanford.edu' #MAIL Server hostname
HOST2 = 'cs.stanford.edu'
USERNAME = 'stats60' #Mailbox username
PASSWORD = 'stats60!' #Mailbox password
MAILBOX_EMAIL = 'stats60@cs.stanford.edu'

# True TA:

#******TRUE_TA_NAME = 'Emre'
TRUE_TA_NAME = 'Andreas'
#******TRUE_TA_EMAIL = 'eorbay@stanford.edu'
TRUE_TA_EMAIL = 'paepcke2000@gmail.com'

TA_NAME_MALE = 'Frank'
TA_EMAIL_MALE = 'netTa%s@cs.stanford.edu' % TA_NAME_MALE
TA_SIG_MALE = 'Best, ' + TA_NAME_MALE

TA_NAME_FEMALE = 'Diane'
TA_EMAIL_FEMALE = 'netTa%s@cs.stanford.edu' % TA_NAME_FEMALE
TA_SIG_FEMALE = 'Best, ' + TA_NAME_FEMALE

ROBO_NAME  = 'RoboTA'
ROBO_EMAIL = 'roboTA@cs.stanford.edu' 
ROBO_SIG = 'Greetings, RoboTA.'

# Will be placed in same dir as this script:
LOG_FILE = 'roboTA.log'

# Where TA's guesses as to the origin
# of each student question's grp assignment
# are stored. Will be placed in same dir as
# this script:
GUESS_RECORD_FILE = 'taGuessRecord.csv'

DO_RETURN_ORIGINAL = True
DONT_RETURN_ORIGINAL = False

ROBO_EMAIL = 'roboTA@cs.stanford.edu'
human_ta_alias = 'networksTA@cs.stanford.edu' #stats60TA@cs.stanford.edu
admin_alias = 'paepcke@cs.stanford.edu'

ssl = False

TEST = None

destination_addrs = [ROBO_EMAIL.lower(), TA_EMAIL_FEMALE.lower(), TA_EMAIL_MALE.lower()]
                         
# Regex pattern to find the "On <date>, <email-add> wrote:" 
# original quote pattern of a return message. Example:
#
#    On Tue, Apr 11, 2017 at 9:45 AM, <networksTA@cs.stanford.edu> wrote:
#
# Always starts with 'On'. Find first string-group up to 
# the email address' "<", then a second string-group 
# from after the ">" to the end of the line: 

EMAIL_QUOTE_FIND_PATTERN = re.compile(r'(^On[^<]*)[^>]*>(.*)', re.MULTILINE)


class EmailChecker(object):

    def __init__(self, logFile=LOG_FILE):
        
        # Path to this script:
        self.script_path = os.path.dirname(__file__)
        if not os.path.isabs(logFile):
            logFile = os.path.join(self.script_path, logFile)
        
        self.log_file = logFile
        self.setupLogging(logging.INFO, self.log_file)

        # Regex for start of first line being H, R, human, Human, Robot, or robot, 
        # followed by \n or \r:
        # This expression is valid for non-HTML text messages:
        self.guess_pattern = re.compile(r'(H)[\n\r]|(R)[\n\r]|(h)[\n\r]|(r)[\n\r]|([hH]uman)[\n\r]|([rR]obot)[\n\r]')
        
        # Same for messages that are HTML, as from MS Outlook:
        self.guess_html_pattern = re.compile(r'^<p>(H)</p>$|^<p>(R)</p>$|^<p>(h)</p>$|^<p>(r)</p>$|^<p>([hH]uman)</p>$|^<p>([rR]obot)</p>$', re.MULTILINE)

        # Regex for removing *****SPAM***** at start of subject:
        self.starSpamPattern = re.compile(r'([^*]*)(\*\*\*\*\*SPAM\*\*\*\*\*)(.*)')

        # Regex for removing [SPAM:####] at start of subject:
        self.sharpSpamPattern = re.compile(r'([^#]*)(\[SPAM:[#]+\])(.*)')
        
        # Regex to find 'Best, TA name' or 'Regards TA name' for 
        # male or female TA:
        self.ta_sig_pattern = re.compile(r'^[\s]*(Best|Regards|Cheers|Greetings){0,1}[,.\s]*(%s|%s|%s|%s)[.]{0,1}[\s]*$' %\
                                         (TRUE_TA_NAME, TA_NAME_MALE, TA_NAME_FEMALE, ROBO_NAME), 
                                         re.IGNORECASE|re.MULTILINE)

        self.robo_sig_pattern = re.compile(r'\n\n' + ROBO_SIG + r'$')

        # Regex to match RoboTA greeting:
        # Find variations of "Dear RoboTA,..." and "Hi RoboTA..." with
        # or without trailing comma:
        self.robo_greeting = re.compile(r'^[\s]*(Dear|Hi)( RoboTA]{0,1}[,]{0,1})',
                                        flags=re.MULTILINE|re.IGNORECASE)

        # Same with TA greeting: "Dear <taName>", "Hi <taName>", ...
        self.ta_greeting = re.compile(r'^[\s]*(Dear|Hi) (%s|%s)[,]{0,1}' % (TA_SIG_MALE, TA_SIG_FEMALE),
                                      flags=re.MULTILINE|re.IGNORECASE) 
        
        # For remembering which student sent
        # original msg to robot/human, and to
        # remember students' email address.
        # Format:  <msgID> ==> (orig_dest, student_email)
                 
        self.traffic_record = shelve.open('traffic_record')
        
        # Build internal database of legitimate student senders:
        self.parse_student_info()

        # Log into the IMAP server. Since we keep 
        # querying it regularly, it seems to
        # stay connected, and we only login once:

        self.login_receiving()

    def login_sending(self):
        '''
        Login into sendmail server
        '''
        self.serverSending = smtplib.SMTP(HOST2,587)
        #*********
        #self.serverSending.set_debuglevel(True)
        #*********
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
        "Best, <taName>". If signature found, removes it.
        
        Else: forwards the TA's response to the student, originating from the
        actor to which the original msg was directed: networksTA or roboTA.
        
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
                if sender != TRUE_TA_EMAIL:
                    # Yes, from student:
                    if sender not in self.student_db:
                        self.logErr('Student not found in database!: %s' % sender)
                        continue
                    self.logInfo('Msg from student: %s to %s' % (sender, dest))
                    
                    # Prepare message to send to TA:
                    
                    msg = MIMEMultipart('alternative')
                    
                    if(msgStringParsed['Content-Transfer-Encoding']=='base64'):
                        body = msgStringParsed.get_payload().decode('base64')
                    else:                    
                        body,_ = self.get_body2(msgStringParsed)
                    # Canonicalize end-of-line to be '\n', not '\r\n':
                    body = body.replace('\r', '')              
                    body = self.ta_greeting.sub('',body)
                    body = self.robo_greeting.sub('',body)
                    #body = self.robo_sig_pattern.sub('',body)
                    subject = self.cleanSubjectOfSpamNotice(msgStringParsed['Subject'])
                    subject = self.ta_greeting.sub(' ',subject)
                    subject = self.robo_greeting.sub(' ',subject)


                    msg.attach(MIMEText(body, 'plain', 'utf-8'))
                    msg['From'] = MAILBOX_EMAIL
                    msg['To'] = TRUE_TA_EMAIL
                    msg['Subject'] = subject + '   RouteNo:' + msg_id
                    
                    # Remember to whom student sent her msg, and her 
                    # return addr:
                    self.traffic_record[msg_id] = (sender, dest)
                    self.traffic_record.sync()
                    
                    # Send this email:
                    self.login_sending()
                    self.serverSending.sendmail(sender, [TRUE_TA_EMAIL], msg.as_string())

                # Email received from HEAD-TA (a reply):
                else:

                    body1,charset    = self.get_body2(msgStringParsed) #@UnusedVariable

                    subject = self.cleanSubjectOfSpamNotice(msgStringParsed['Subject'])
                    date    = msgStringParsed['Date']

                    body=body1
                    # Canonicalize end-of-line to be '\n', not '\r\n':
                    body = body.replace('\r', '')                    
                    # First line of body is to be a line that
                    # is empty except for the human/robot guess:

                    match_non_html = self.guess_pattern.match(body)
                    match_html     = self.guess_html_pattern.match(body)
                    if match_non_html is None and match_html is None:
                        # Could not find the expected guess:
                        new_body = 'NO H or R IN FIRST LINE!\n' + self.msg_subj_plus_body(date,subject,body)
                        self.admin_msg_to_ta('noGuess', new_body)
                        continue
                    else:
                        if match_non_html is not None:
                            ta_guess = match_non_html.group().strip()
                            # Remove the guess from the body before sending
                            # on to the student:
                            body = body[len(ta_guess):]   
                            
                        else:
                            # The gues was embedded in damn MS Outlook mess:
                            for (grp, i) in enumerate(match_html.groups()):
                                if grp is not None:
                                    guess_start = match_html.start(i)
                                    guess_end   = match_html.end(i)
                                    ta_guess = grp
                                    break
                            body = body[:guess_start] + body[guess_end:]
   
                    body = self.remove_sig_if_exists(body)
                                            
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
                            #  del self.traffic_record[orig_msg_id]
                            self.traffic_record.sync()
                        except:
                            pass
                     
                    # Record the original destination as the truth the TA was to guess:
                    self.record_ta_guess(date, msg_id, orig_dest, guess=ta_guess)
                    # print body


                    # Sign the return:
                    if orig_dest.lower() == ROBO_EMAIL.lower():
                        if '________________________________' in body:
                            body = body.split('________________________________')[0] + '\n%s' % ROBO_SIG +'\n________________________________'+ body.split('________________________________')[1] 
                        else: body += '\n\n%s' % ROBO_SIG

                    elif orig_dest.lower() == TA_EMAIL_FEMALE.lower():
                        if '________________________________' in body:
                            body = body.split('________________________________')[0] + '\n%s' % TA_SIG_FEMALE + '\n________________________________'+ body.split('________________________________')[1] 
                        else: body += '\n\n%s' % TA_SIG_FEMALE

                    else:
                        if '________________________________' in body:
                            body = body.split('________________________________')[0] + '\n%s' % TA_SIG_MALE + '\n________________________________'+ body.split('________________________________')[1] 
                        else: body += '\n\n%s' % TA_SIG_MALE


                    msg = MIMEMultipart('alternative')

                    msg['From'] = orig_dest
                    msg['Subject'] = subject
                    msg['To'] = ''
                    
                    # Body will contain the quoted original message;
                    # something like:
                    #          <text of reply>
                    #    On Tue, Apr 11, 2017 at 9:45 AM, <networksTA@cs.stanford.edu> wrote:
                    # where the email address is human_ta_alias. 
                    # Replace that with the original student sender:
                    
                    match = EMAIL_QUOTE_FIND_PATTERN.search(body)
                    if match is not None:
                        # Get tuple (begin,end) of first group.
                        # The end index points to just before the
                        # opening '<' of the email msgs. Match.span(group#)
                        # returns that tuple:
                        
                        up_to        = match.span(1)[1] # pt to "<networksTA@..."
                        then_to_end  = match.span(2)[0] # pt to after the closing ">"
                        
                        body = body[:up_to] + '<' + student_sender + '>' + body[then_to_end:]
                    
                    msg.attach(MIMEText(body, 'plain', 'utf-8'))
                    self.logInfo('%s replying to: %s' % (msg['From'], student_sender))

                    self.login_sending()
                    # Use destination of student's original msg
                    # as sender in this sendmail call. That will either
                    # be robota@cs.stanford.edu, or networksta@cs.stanford.edu.
                    # In any case: this needs to be a xxx@cs.stanford.edu address!
                    # Else CS mail server silently drops the msg: 
                    
                    self.serverSending.sendmail(orig_dest, [student_sender], msg.as_string())

            except Exception as e:
                    self.logErr('This error in runScript() loop: %s' % `e`)
                    continue
                    raise
        return 1

    def remove_sig_if_exists(self, body):
        '''
        If true-ta accidentally added a signature somewhere
        in their message, then remove it. The regex finds
        "Best, <name" and "Regards, <name>" and "Cheers, <name>"
        
        @param body: Body of email from TA, destined back to student 
        @type body: string
        '''
        
        # Did TA accidentally sign his/her name?
        sig_match = self.ta_sig_pattern.search(body)
        
        # For a message body containing something like
        #    Best, Diane
        # the match object will contain several groups,
        # such as ("Best", "Diane"). Delete everything
        # from the start of the first group to the 
        # end of the last. Some groups may be none,
        # for the case where the sig is just:
        #    Diane
        # In the case the groups will be (None, 'Diane')
        
        if sig_match is not None:
            
            sig_start = 0
            
            # Start of what's to be removed will be 
            # the first position of the first non-None 
            # regex group:
            
            for nth, matched_str in enumerate(sig_match.groups()):
                if matched_str is None:
                    continue
                sig_start = sig_match.span(nth)[0]
                break
            
            sig_end = 0
            
            # End of what's to be removed will be 
            # the last position of the *last* non-None 
            # regex group:
            for nth, matched_str in enumerate(reversed(sig_match.groups())):
                if matched_str is None:
                    continue
                sig_end = sig_match.span(nth)[1]
                break
            
            # Surgically remove the signature:
            body     = body[:sig_start] + body[sig_end:]

        return body
        
        
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
        if true_origin == human_ta_alias:
            true_origin = 'human'
        else:
            true_origin = 'robot'
            
        # Same for the guess: could the h, H, Human, human, R, r, Robot, or robot:
        if guess[0] in ['R','r']:
            guess = 'robot'
        else:
            guess = 'human'
            
        # Path to csv file where we record TA guesses
        # of origin:
        guess_path = os.path.join(self.script_path, GUESS_RECORD_FILE)            
            
        # If TA-guess csv file doesn't exist yet,
        # create the file with column header at the top:
        if not os.path.exists(guess_path):
            with open(guess_path, 'w') as fd:
                fd.write('date,msg_id,true_origin,guessed_origin\n')
        
        with open(guess_path, 'a') as fd:
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
                    text = payload.get_payload()
                    #print text
                    if(self.contains_non_ascii_characters(text)):
                        return MIMEText(text.encode('utf-8'),'plain','utf-8') 
                    else:
                        return MIMEText(text,'plain')
                else:
                    html = payload.get_payload()
                    #print html
                    if self.contains_non_ascii_characters(html):
                            return MIMEText(html.encode('utf-8'), 'html','utf-8')
                    else:
                            return MIMEText(html, 'html')  

        else: 
            if email_msg.get_content_maintype() == 'text':
                text = email_msg.get_payload()
                if(self.contains_non_ascii_characters(text)):
                    return MIMEText(text.encode('utf-8'),'plain','utf-8') 
                else:
                    return MIMEText(text,'plain')
            else:
                    html = email_msg.get_payload()
                    if self.contains_non_ascii_characters(html):
                            return MIMEText(html.encode('utf-8'), 'html','utf-8')
                    else:
                            return MIMEText(html, 'html')  

    
    def get_body2(self,email_msg):
        '''
        Dig body out of a raw email string.
        
        :param email_msg: raw email
        :type email_msg: string
        :return just the message body
        '''
        text = ""
        if email_msg.is_multipart():

            #html = None
            for payload in email_msg.get_payload():
                if payload.get_content_charset() is None:
                # We cannot know the character set, so return decoded "something"
                    text = payload.get_payload(decode=True)
                    continue
                charset = payload.get_content_charset()
                if payload.get_content_maintype() == 'text':
                    return (unicode(payload.get_payload(decode=True), 
                                   str(charset), 
                                   "ignore").encode('utf8', 'replace'),
                            charset)

        else:
            payload = email_msg.get_payload(decode=True)
            charset = str(email_msg.get_content_charset()), 
            text = unicode(unicode(payload.get_payload(decode=True),
                           charset,
                           'ignore').encode('utf8', 'replace')
                           )
            return (text, charset)
            
        
    def contains_non_ascii_characters(self,theStr):
        return not all(ord(c) < 128 for c in theStr)  

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

        self.student_ta = {'1':ROBO_EMAIL,
                           '2':human_ta_alias}

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
        msg = MIMEMultipart('alternative')
        msg['From'] = admin_alias
        msg['To'] = TRUE_TA_EMAIL
        # Stick student ID into msg header:
        msg['Subject'] = 'You Screwed Up, Dude: %s' % errorStr
        body += 'Problem: %s\n' % errorStr
        msg.attach(MIMEText(body, 'html','utf-8'))
        self.logErr(TRUE_TA_NAME + ' error: %s' % errorStr)
        self.login_sending()
        self.serverSending.sendmail(sender, [TRUE_TA_EMAIL], msg.as_string())

        
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

    def log_program_stop(self, reason='Received cnt-c; stopping mail check server.'):
        '''
        Called to enter a note in the log that
        the program was stopped. Called from 
        main() when SIGINT is caught.
        '''
        self.logInfo(reason)

            
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

