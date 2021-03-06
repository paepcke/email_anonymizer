
#from email.base64mime import body_decode
'''
Module for relaying messages between students and robot/TA.

'''
# The imap box:

import csv
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import imaplib
import logging
import os
import re
import smtplib
import sys
from urllib import quote, unquote

from mock.mock import self

from traffic_memory import TrafficMemory


HOST = 'cs-imap-x.stanford.edu' #MAIL Server hostname
HOST2 = 'cs.stanford.edu'
USERNAME = 'stats60' #Mailbox username
IMAP_PWD_FILE = 'imap_password.txt'          # File containing imap password in ~/.ssh
MAILBOX_EMAIL = 'stats60@cs.stanford.edu'

# True TA:

TRUE_TA_NAME = 'Emre'
#******TRUE_TA_NAME = 'Andreas'
TRUE_TA_EMAIL = 'eorbay@stanford.edu'
#******TRUE_TA_EMAIL = 'paepcke2000@gmail.com'

TA_NAME_MALE = 'Frank'
TA_EMAIL_MALE = 'netTa%s@cs.stanford.edu' % TA_NAME_MALE
TA_SIG_MALE = 'Best, ' + TA_NAME_MALE

TA_NAME_FEMALE = 'Diane'
TA_EMAIL_FEMALE = 'netTa%s@cs.stanford.edu' % TA_NAME_FEMALE
TA_SIG_FEMALE = 'Best, ' + TA_NAME_FEMALE

ROBO_NAME  = 'RoboTA'
ROBO_EMAIL = 'roboTA@cs.stanford.edu' 
ROBO_SIG = 'Greetings, ' + ROBO_NAME

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

ssl = False

TEST = None

destination_addrs = [ROBO_EMAIL.lower(), TA_EMAIL_FEMALE.lower(), TA_EMAIL_MALE.lower()]
                         
# Regex pattern to find the "On <date>, <email-add> wrote:" 
# original quote pattern of a return message. Example:
#
#    On Tue, Apr 11, 2017 at 9:45 AM, <stats60@cs.stanford.edu> wrote:
#
# Always starts with 'On'. Find first string-group up to 
# but excluding the email address: "<", then a second 
# string-group that is the email address, excluding the 
# closing ">". And a third group from after the email-closing
# ">". The groups are named: 'intro', 'email', 'trailer'.

#EMAIL_QUOTE_FIND_PATTERN = re.compile(r'(^On[^<]*)[^>]*>(.*)', re.MULTILINE)
EMAIL_QUOTE_FIND_PATTERN = re.compile(r'(?P<intro>^[>\s]*On[^<]*)<(?P<email>[^>]*)>(?P<trailer>.*)', re.MULTILINE)


class EmailChecker(object):

    def __init__(self, logFile=LOG_FILE):
        
        self.imap_pwd = self.get_password_from_file()
        
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
        
        # Regex to find "Best, TaName" or 'Regards TaName' for 
        # male, female, or robo- TA. The (?P<greeing>...) and
        # (?P<taName>...) groups are named (with names 'greeting'
        # and 'taName') so we can refer to the captured strings
        # by name later:
        #****self.ta_sig_pattern = re.compile(r'^[\s]*(?P<greeting>Best|Regards|Cheers|Greetings){0,1}[,.\s]*(?P<taName>%s|%s|%s|%s)[.]{0,1}[\s]*$' %\
        self.ta_sig_pattern = re.compile(r'^[\s]*(?P<greeting>Best|Regards|Cheers|Greetings){0,1}[,.\s]*(?P<taName>%s|%s|%s|%s)(?P<clutter>[.]{0,1}[\s]*)$' %\
                                         (TRUE_TA_NAME, TA_NAME_MALE, TA_NAME_FEMALE, ROBO_NAME), 
                                         re.IGNORECASE|re.MULTILINE)

        self.robo_sig_pattern = re.compile(r'\n\n' + ROBO_SIG + r'$')

        # Same with TA greeting: "Dear <taName>", "Hi <taName>", ...
        self.ta_greeting = re.compile(r'^[\s]*(Dear|Hi|Greetings|Hello|Hey){0,1}[,]{0,1}[\s]*(%s|%s|%s)[.,]{0,1}[\s]*' %\
                                     (TA_NAME_MALE, TA_NAME_FEMALE, ROBO_NAME),
                                      flags=re.MULTILINE|re.IGNORECASE) 

        # Placeholder to use when hiding the email address
        # in the headers of emails with threads. As in: 
        #     "On <date> <roboTA@cs.stanford.edu>:
        # Must lose the email address: 
        self.email_obscuration = '<***email_obscured***>'
        
        # Analogously for TA or Robot signatures 
        # in threads:
        self.sig_obscuration   = '<***sig_obscured***>'

        # Recognize a TA- or Robo signature in text:
        self.ta_robo_sig_pattern = re.compile(r'(%s|%s|%s)[.]{0,1}' % (TA_SIG_MALE, TA_SIG_FEMALE, ROBO_SIG))

        # Recognize whether a subject line has
        # a routing number included. That would
        # show that the msg is a reply from the TA:
        self.subject_routeNo_pattern = re.compile(r'RouteNo:<[^@]*@[^>]*>$')
        
        # For remembering which student sent
        # original msg to robot/human, and to
        # remember students' email address.
        # Format:  <msgID> ==> (orig_dest, student_email)
        # This persistent dict writes to disk on
        # each action:
                 
        self.traffic_record = TrafficMemory('traffic_record')
        
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
        self.serverSending.login(USERNAME, self.imap_pwd)
        
    def logout_sending(self):
        self.serverSending.quit()

    def login_receiving(self):
        '''
        Log into the IMAP server.
        '''
        self.serverReceiving = imaplib.IMAP4_SSL(HOST, 993)
        self.serverReceiving.login(USERNAME, self.imap_pwd)

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

                sender = msgStringParsed['From']
                # Sender may be true-name+email, or just email, such as:
                #    'John Doe <doe@gmail.com>'
                # vs  'doe@gmail.com'
                # Handle both:
                sender = sender.split('<')
                if len(sender) > 1:
                    sender = sender[1][:-1]
                else:
                    sender = sender[0]
                
                dest   =  msgStringParsed['To']
                subject = self.cleanSubjectOfSpamNotice(msgStringParsed['Subject'])
                msg_id =  msgStringParsed['Message-ID']

                ## Email received from student?
                # We recognize messages from the TA
                # by the subject line containing the
                # original student msg's routing number.
                # Using the criterion "if not from TA email
                # address it's a student won't work
                # when TA re-sends a response after adding
                # the guess. Also: TA might have a default
                # REPLY-TO that is not the same as TRUE_TA_EMAIL:
                
                
                if self.subject_routeNo_pattern.search(unquote(subject)) is None:
                    # Yes, from student, since no routing no in subject.
                    if sender not in self.student_db:
                        self.logErr("Student not found in database!: '%s'" % sender)
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
                    
                    body = self.remove_greeting_if_exists(body)
                    # Replace emails in thread headers:
                    #   On <date> <roboTA@cs....> wrote:
                    # with ...<****obscured_email***>:
                    
                    body = self.obscure_thread_headers(body)
                    
                    # Similarly: obscure any robo or TA 
                    # signatures in the depth of threads:
                    
                    body = self.obscure_thread_sigs(body)
                    
                    subject = self.remove_greeting_if_exists(subject)
                    
                    # If this is a whole thread, need to obscure the
                    # turn-headers before sending this student email
                    # to the TA. Example:
                    #
                    #    On Mon, Apr 17, 2017 at 10:29 AM, <roboTA@cs.stanford.edu> wrote:
                    body = self.obscure_thread_headers(body)

                    msg.attach(MIMEText(body, 'plain', 'utf-8'))
                    msg['From'] = MAILBOX_EMAIL
                    msg['To'] = TRUE_TA_EMAIL
                    msg['Subject'] = self.join_subject_and_routing_number(subject, msg_id)
                    
                    # Remember to whom student sent her msg, and her 
                    # return addr:
                    self.traffic_record[msg_id] = (sender, dest)
                    
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

                    body = self.remove_sig_if_exists(body)
                                            
                    # Recover dest of original address from x-student-dest header field:
                    (orig_subject, orig_msg_id) = self.recover_route_number(subject)
                    (student_sender, orig_dest) = self.traffic_record.get(orig_msg_id, (None, None))
                    
                    # Record the original destination as the truth the TA was to guess.
                    # This method also digs out the TAs guess and sends a
                    # msg to them if no guess is found:  
                    
                    body = self.register_ta_guess(orig_subject, body, date, orig_msg_id, orig_dest)
                    if body is None:
                        # TA forgot to guess:
                        continue   
                    
                    # Restore any thread headers we find that have
                    # been obscured: 'On <date> <****obscured_email***> wrote:...
                    # Replace the email_obscuration with the email address to
                    # which the student sent their original msg:
                    
                    body = self.recover_thread_headers(body, orig_dest, student_sender)
                    
                    # Restore TA/Robo signatures embedded in threads that
                    # were obfuscated to blind the TA:
                    
                    body = self.recover_thread_sigs(body, orig_dest)
                    
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
        return 1

    def remove_sig_if_exists(self, body):
        '''
        If true-ta accidentally added a signature somewhere
        in their message, then remove it. The regex finds
        "Best, <name" and "Regards, <name>" and "Cheers, <name>"
        
        @param body: Body of email from TA, destined back to student 
        @type body: string
        @return: new body string without the signature.
        @rtype: string
        '''
        
        # Did TA accidentally sign his/her name?
        sig_match = self.ta_sig_pattern.search(body)
        
        # For a message body containing something like
        #    Best, Diane
        # or
        #    Cheers, Frank.
        # the match object will contain several groups,
        # such as ("Best", "Diane"). Delete everything
        # from the start of the first group to the 
        # end of the last. Some groups may be none,
        # for the case where the sig is just:
        #    Diane
        # In the case the groups will be (None, 'Diane')
        
        if sig_match is not None:
            
            sig_start = 0
            sig_end   = 0
            greeting_span = sig_match.span('greeting')
            ta_name_span  = sig_match.span('taName')
            # punctuation and/or whitespace after the name
            clutter_span  = sig_match.span('clutter')
              
            if greeting_span == (-1,-1):
                # Sig was just something like 'Diane',
                # rather than 'Regards, Diane'. Get
                # the start/end tuple of the name
                # (e.g. (15,20) if 'Diane' started
                # at pos 15 in the body):
                sig_start = ta_name_span[0]
            else:
                # There is a greeting; start of sig
                # is the start of that greeting:
                sig_start = greeting_span[0]
            
            if clutter_span == (-1,-1):  
                # End of sig is the end of the TA-name group:
                sig_end = ta_name_span[1]
            else:
                sig_end = clutter_span[1]

            # Surgically remove the signature:
            body     = body[:sig_start] + body[sig_end:]

        return body
    
    def remove_greeting_if_exists(self, the_text):
        '''
        Remove any greeting at the start of a student's
        request. Handles greetings like:
          - Hi, RoboTA
          - Hello Frank,
          - Hey, Diane.

        @param the_text: email message the_text
        @type the_text: string
        @return: new the_text string without the greeting.
        @rtype: string
        '''

        the_text = self.ta_greeting.sub('',the_text)
        return the_text
    
    def obscure_thread_headers(self, body):
        '''
        Given a body that contains one or more lines like:
        
          On Mon, Apr 17, 2017 at 10:29 AM, <roboTA@cs.stanford.edu> wrote:
        or
          On Mon, Apr 17, 2017 at 10:29 AM, <netTaDiane@cs.stanford.edu> wrote:
        
        replace the address with something easily found again.
        That way the dual of this method: recover_thread_headers()
        has an easier job. We replace the address with
        self.email_obscuration. Thread headers from students remain untouched.
        
        @param body: entire email message body
        @type body: string
        @return: copy of body with emails in thread header replaced
            by self.email_obscuration.
        @rtype: string 
        '''
        new_body = ''
        cursor = 0
        # pattern.finditer(str) gives a tuple of match
        # objects. In our case, each match object holds
        # three named groups: intro, email, and trailer.
        # Go through them and copy all but the emails to
        # new_body
        for match in EMAIL_QUOTE_FIND_PATTERN.finditer(body):
            # Is this thread header from a TA or the Robot?
            if match.group('email') not in [ROBO_EMAIL, TA_EMAIL_FEMALE, TA_EMAIL_MALE]:
                continue
            # Yes, need to obscurate:
            (intro_start, intro_end)     = match.span('intro') #@UnusedVariable
            (trailer_start, trailer_end) = match.span('trailer')

            new_body += body[cursor:intro_end] +\
                        self.email_obscuration +\
                        body[trailer_start:trailer_end]
            cursor = trailer_end
        new_body += body[cursor:]
        return new_body    

    def recover_thread_headers(self, body, assigned_ta_email, student_email):
        '''
        Given an email from the TA that is part of 
        a multi-msg thread, restore the thread headers
        for the student to see. Ex.: all thread headers
        that were obfuscated by obscure_thread_headers()
        are turned from the obfuscated form:
        
            On Mon, Apr 17, 2017 at 10:29 AM, <***obscured***> wrote:
            
        To their original:
            On Mon, Apr 17, 2017 at 10:29 AM, <roboTA@cs.stanford.edu> wrote:
        Also: the emails in thread headers with email address 
        'stats60@cs.stanford.edu' are replaced with the inquiring 
        student's address.
        
        @param body: email message the_text
        @type body: string
        @param assigned_ta_email: email address of TA to which
            the student was assigned. Ex.: roboTA@cs.stanford.edu
        @type assigned_ta_email: string
        @param student_email: email address of inquiring student
        @type student_email: string 
        @return: new body string with the origin addresses
            in thread headers replaced with proper sender
        @rtype: string
        '''
        new_body = body.replace(self.email_obscuration, '<%s>' % assigned_ta_email)
        new_body = new_body.replace(MAILBOX_EMAIL, '%s' % student_email)
        return new_body
        
    def obscure_thread_sigs(self, body):
        '''
        Find all TA- or Robo- signatures in 
        quoted, multi-exchange threads and 
        replace them with a placeholder:
        self.sig_obscuration
        
        @param body: email message body
        @type body: string
        @return: modified email body with signatures replaced
            by self.sig_obscuration
        @rtype: string 
        '''
        


        new_body = ''
        cursor = 0
        # pattern.finditer(str) gives a tuple of match
        # objects. In our case, each match object holds
        # one groups, a greeting by the male/female
        # TA, or a Robo sig.

        for match in self.ta_robo_sig_pattern.finditer(body):
            (sig_start, sig_end)     = match.span(1) #@UnusedVariable
            new_body += body[cursor:sig_start] + self.sig_obscuration
            cursor = sig_end
        new_body += body[cursor:]
        return new_body    
        
    def recover_thread_sigs(self, body, orig_dest_email):
        '''
        Given an email body in which TA or robo signatures
        were obfuscated in the thread, restore the original
        signatures.
        
        @param body: the body with obscurated signatures
        @type body: string 
        @param orig_dest_email:
        @type orig_dest_email:
        @return: modified email body with signatures recovered.
        @rtype: string 
        '''
        if orig_dest_email == TA_EMAIL_MALE:
            sig = TA_SIG_MALE 
        elif orig_dest_email == TA_EMAIL_FEMALE:
            sig = TA_SIG_FEMALE
        else:
            sig = ROBO_SIG
            
        new_body = body.replace(self.sig_obscuration, '%s' % sig)
        return new_body
        
    def persist_ta_guess(self, date, msg_id, true_origin, guess):
        '''
        Write the TA's guess as to destination intent of student message
        to a log. Normalizes the flexible first-line guesses (r,R,human,Robot, etc.)
        to 'human' and 'robot'. 
        
        :param date: date of the original message
        :type date: string
        :param msg_id: message header msg-id
        :type msg_id: string
        :param true_origin: student's email address TO field. I.e.
            the email that indicates the student's experiment
            group membership.
        :type true_origin: string
        :param guess: the TA guess as recorded on first line of return.
        :type guess: string
        '''
        
        # true_origin is the email of the roboTA or 
        # the male or female fake TA:
        # Normalize that into: 'robot' and 'human'
        if true_origin == TA_EMAIL_FEMALE or true_origin == TA_EMAIL_MALE: 
            true_origin = 'human'
        else:
            true_origin = 'robot'
            
        # Same for the guess: could be h, H, Human, human, R, r, Robot, or robot:
        if guess in ['R','r', 'Robot', 'robot']:
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

    def register_ta_guess(self, orig_subject, body, date, orig_msg_id, true_origin, testing=False):
        '''
        Given an email body from the true TA, 
        destined for the student who asked the
        respective question, find the TA's 
        participant group guess in the first 
        line of the message. The guess is any
        of 'R', 'H', 'Robot', or 'Human' in
        upper or lower case. 
        
        If the guess not there, send a 
        fix-it message to the TA, and return 
        None. Else return the TA's message body 
        with the guess removed.
        
        Handles messages from both, normal mail clients
        and from outlook.
         
        @param orig_subject: the orig_subject line of the msg
            that came in from the student.
        @type suject: string
        @param body: text of the message from the TA 
        @type body:
        @param date: message date
        @type date: string
        @param orig_msg_id: original message id of question by student
        @type orig_msg_id: string
        @param true_origin: the actual experiment group
            that the sending student is in.
        @type true_origin: string
        @param testing: if True then method won't call
            persist_ta_guess(), nor will the TA correction
            request message be created and sent. 
            Used for unit testing this method.
        @type testing: boolean     
        @return: {None | body with guess removed}
        @rtype: {None | string}
        '''
        
        # First line of body is to be a line that
        # is empty except for the human/robot guess:

        match_non_html = self.guess_pattern.match(body)
        match_html     = self.guess_html_pattern.match(body)
        
        if match_non_html is None and match_html is None:
            
            # Could not find the expected guess. 
            # Explain to TA how to resend the message,
            # making it easy: just copy/paste. The 
            # '\r' chars are needed (at least) for 
            # gmail on Firefox and Chrome:
            if not testing:
                subject_with_msg_id = self.join_subject_and_routing_number(orig_subject, orig_msg_id)
                self.admin_msg_to_ta_with_return(subject_with_msg_id, body, msg_to_ta='You forgot to guess message origin (human/robot). ')
            return None
        else:
            if match_non_html is not None:
                ta_guess = match_non_html.group()
                # Remove the guess from the body before sending
                # on to the student:
                body = body[len(ta_guess):]
                ta_guess = ta_guess.strip()
                
            else:
                # The gues was embedded in damn MS Outlook mess:
                for (grp, i) in enumerate(match_html.groups()):
                    if grp is not None:
                        guess_start = match_html.start(i)
                        guess_end   = match_html.end(i)
                        ta_guess = grp
                        break
                # Remove the guess from the body before sending
                # on to the student:
                body = body[:guess_start] + body[guess_end:]

            # Remember the true student membership and the TA's guess:
            if not testing:                
                self.persist_ta_guess(date, orig_msg_id, true_origin, ta_guess)
        return body        

    def admin_msg_to_ta_with_return(self, 
                                    orig_subject, 
                                    body, 
                                    msg_to_ta=None,
                                    testing=False):
        '''
        Sends message to TA, providing them with 
        a message that includes a mail-to link that
        contains the template for an email back a
        student who asked a question. If msg_to_ta
        is non-None, it will be prepended to the 
        mail-to link. 
        
        Used, for instance, when TA responds to a student, 
        but forgets the guess at the top of the msg.
        Then a msg_to_ta might say: "Forgot the guess."
        The ta would receive an email with the given
        orig_subject line, and:
           Forget the guess. <mailToLink>Click here to fix and resend</mailToLink>
        where the mailToLink, when clicked, starts an
        email that allows TA simply to add the guess, 
        and send again.
        
        @param orig_subject: orig_subject line as it should appear
            on TA's resend.
        @type orig_subject: string
        @param body: text as it appeared in the msg from the TA
        @type body: string
        @param testing: if true, message won't actually be
            sent, but its would-be body is returned.
        @type testing: bool
        @return: body as it was sent
        @rtype: string
        '''
        
        if msg_to_ta is None:
            msg_to_ta = ''
        # Make the body url-legal:
        body = quote(body)
        
        mailto_link = '<a href="mailto:%s?subject=%s&body=%s">Click here to fix and resend.</a>' %\
            (MAILBOX_EMAIL, orig_subject, body)
        
        # The message that the TA will see:
        #    Message from relay: <errorMsg>
        #    Click here to fix and resend.
        # Where the second line below will be 
        # a mail-to that generates the proper
        # return email to the relay:
        
        msg = "Message from relay: %s<br>%s" % (msg_to_ta, mailto_link)
        if not testing:
            self.admin_msg_to_ta(msg, orig_subject)
        return msg

    def admin_msg_to_ta_error(self, body, errorStr):
        '''
        Send an error msg to TA, logging the error.
        Ensures that TA replying does not go to students.
        
        :param body: body of msg to send
        :type body: string
        :param errorStr: very short keyword that indicates error condition;
            the string is appended to the 'This is an error' subject
            line, and used in the error log.
        :type errorStr: string
        '''
        subject = 'You Screwed Up, Dude: %s' % errorStr
        self.logErr(TRUE_TA_NAME + ' error: %s' % errorStr)
        self.admin_msg_to_ta(body, subject)

    def admin_msg_to_ta(self, body, subject):
        '''
        Send a msg to TA with out-of-band information.
        Ensures that TA replying does not go to students.
        
        :param body: body of msg to send
        :type body: string
        :param subject: subject line
        :type subject: string
        '''
        
        sender = TRUE_TA_EMAIL
        msg = MIMEMultipart('alternative')
        msg['From'] = MAILBOX_EMAIL
        msg['To'] = MAILBOX_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html','utf-8'))
        #msg.attach(MIMEText(body, 'plain','utf-8'))
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

    def join_subject_and_routing_number(self, subject, routing_number):
        '''
        Given an email subject line and an email
        message ID, append "RouteNo:<message_id>"
        to the subject line. The message_id will
        be URL encoded. So plus signs are replaced
        with a code that can be recovered by
        recover_route_number().
        
        @param subject: subject line without routing number
        @type subject: string
        @param routing_number: the routing number, such as
            <CAFK+knh...@mail.gmail.com>
        @type routing_number: string
        '''
        
        return subject + ' RouteNo:' + quote(routing_number)

    def recover_route_number(self, subject_with_route_number):
        '''
        Given a subject line to which the message
        ID of an initial student question's email
        was added, return a tuple: the original
        subject string without the routing number,
        and the clear-text un-URL-encoded routing
        number
        
        @param subject_with_route_number: the original subject
            line string with the urlencoded routing number
            appended.
        @type subject_with_route_number: string
        @return: tuple with original subject text, and 
            the clear-text routing number
        @rtype: (string, string)
        '''
        
        # Recover dest of original address from x-student-dest header field:
        (orig_subject, orig_msg_id) = subject_with_route_number.split('RouteNo:')
        return (orig_subject, unquote(orig_msg_id))
        
    def get_password_from_file(self):
        # Get mailbox password from ~/.ssh/imap_pwd.txt
        try:
            with open(os.path.join(os.getenv('HOME'), '.ssh', IMAP_PWD_FILE)) as fd:
                return fd.read().strip()
        except IOError:
            print('Cannot read pwd from ~/%s. Nothing sent.' % IMAP_PWD_FILE)
            sys.exit(1)

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

