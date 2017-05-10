#!/usr/bin/env python
'''
Created on Apr 18, 2017

@author: paepcke

TODO:
  -  catch   raise SMTPServerDisconnected('please run connect() first')
       SMTPServerDisconnected: please run connect() first
'''
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import re
import signal
from smtplib import SMTPServerDisconnected, SMTPRecipientsRefused
import smtplib
import sys
import threading


# The imap box:
HOST = 'cs-imap-x.stanford.edu' #MAIL Server hostname
HOST2 = 'cs.stanford.edu'
USERNAME = 'stats60' #Mailbox username
MAILBOX_EMAIL = 'stats60@cs.stanford.edu'
IMAP_PWD_FILE = 'imap_password.txt'          # File containing imap password in ~/.ssh

FROM_ADDR = 'Phil Levis <pal@cs.stanford.edu>'  # Phil Levis
FROM_NAME = 'Phil Levis'
REPLY_TO  = 'Emre Orbay <emre_research@cs.stanford.edu>'

# In verbose mode, print progress every nth sent email:
REPORTING_INTERVAL = 50
#REPORTING_INTERVAL = 1

class BulkMailer(threading.Thread):
    '''
    Given a file with email addresses, 
    send them. Messages are sent in batches
    of size batch_size. A delay of inter_msg_delay
    seconds is introduced between sending each
    message. Between batches, inter_batch_delay minutes
    will be introduced with no sending
    
    The email_addr_file should contain one email
    address per line. The email address must be
    the first non-space string in each line. It is
    OK to have information after the email address,
    separated by whitespace.
    
    Lines beginning with a hash mark '#' are ignored.
    
    The mailer remembers the last email that
    was sent in a file. If that file is found on startup,
    the mailer checks on the command line whether 
    to resume after that email.
    
    '''
    
    def __init__(self,
                 email_body_file,
                 email_addr_file, 
                 batch_size=200,
                 inter_msg_delay=1,     # seconds
                 inter_batch_delay=10,  # minutes
                 verbose = True,
                 unit_test_case_obj=None
                 ):
        '''
        
        @param email_body_file: file containing complete body of the mailing
        @type email_body_file: string
        @param email_addr_file: file with destination email addresses
        @type email_addr_file: string
        @param batch_size: number of messages to send before a long pause 
        @type batch_size: int
        @param inter_msg_delay: seconds to wait between each msg
        @type inter_msg_delay: int (seconds)
        @param inter_batch_delay: minutes to wait between batches
        @type inter_batch_delay: int (minutes)
        @param verbose: if True, prints progress every REPORTING_INTERVAL
            emails
        @type verbose: boolean
        @param unit_test_case_obj: set to an instance of the pyunit 
            TestCase object if this class is instantiated
            for unit unit_test_case_obj. No email will be sent. But whenever
            an email would be sent, a callback to unit_test_case_obj.sending(email_addr)
            will be made. 
        @type unit_test_case_obj: unittest.TestCase
        
        '''

        super(BulkMailer, self).__init__()

        self.email_addr_file = email_addr_file
        self.batch_size = batch_size
        self.inter_msg_delay = inter_msg_delay
        self.inter_batch_delay = inter_batch_delay * 60 # Convert to minutes
        self.verbose = verbose
        self.unit_test_case_obj = unit_test_case_obj
        
        self.imap_pwd = self.get_password_from_file()
        # ***********
        print('Pwd: %s' % self.imap_pwd)
        sys.exit()
        # ***********

        # Recognize an email address as the first
        # not-whitespace substring in a string:
        self.email_addr_pattern = re.compile(r'''^[\s]*          # Leading white space OK
                                                 ([^\s#,]+){1,1}  # Capture One series of chars that are not whitespace, comma, or a comment char
                                                 .*$             # Arbitrary stuff afterwards.
                                              ''', re.VERBOSE) 

        # Recognize comments in the address file:
        self.comment_pattern = re.compile(r'''^[\s]*    # Leading whitespace OK
    	                                      [#]+      # Then at least one '#'
    	                                      .*$       # Followed by anything.
                        	               ''', re.VERBOSE)       
        
        #self.email_addr_pattern = re.compile(r'^[\s]*([^\s#,]+){1,1}.*$')        
                
        self.resume_place_file = os.path.join(os.path.dirname(__file__), 'resume_place_file.txt')
        
        if not os.access(email_body_file, os.R_OK):
            print('Body file %s does not exist or is not readable.' % email_body_file)
            sys.exit(1)
        else:
            with open(email_body_file, 'r') as body_fd:
                self.body = body_fd.read() 
        
        if not os.access(email_addr_file, os.R_OK):
            print('Addr file %s does not exist or is not readable.' % email_addr_file)
            sys.exit(1)
            
        if batch_size < 0 or inter_batch_delay < 0 or inter_msg_delay < 0:
            print('Batch size, and delays must be positive numbers')
            sys.exit(1)

        self.end_bulk_mailer = False
        
        # Condition object for the run() method
        # to sleep on, while still having the 
        # ability to woken by the cnt-c signal
        # handler:
        
        self.wait_condition = threading.Condition()
        
    def get_password_from_file(self):
        # Get mailbox password from ~/.ssh/imap_pwd.txt
        try:
            with open(os.path.join(os.getenv('HOME'), '.ssh', IMAP_PWD_FILE)) as fd:
                return fd.read().strip()
        except IOError:
            print('Cannot read pwd from ~/%s. Nothing sent.' % IMAP_PWD_FILE)
            sys.exit(1)
        
    def run(self):
        
        
        batch_len = 0
        addr      = 'nothing-sent'
        most_recently_sent = None
        self.num_sent = 0
        self.delete_history = False
        
        # Check whether a 'resume' file exists:
        if os.access(self.resume_place_file, os.R_OK) and os.path.getsize(self.resume_place_file) > 0:
            with open(self.resume_place_file, 'r') as fd:
                last_sent_and_num_sent = fd.readline().strip() 
                (most_recently_sent, self.num_sent) = last_sent_and_num_sent.split(',')
                self.num_sent = int(self.num_sent)
                if not self.query_yes_no("Start not at beginning, but after email #%s '%s'?" %\
                                         (self.num_sent, most_recently_sent)):
                    most_recently_sent = None
                    self.num_sent = 0
                    if self.query_yes_no("Forget history of what's been sent?"):
                        self.delete_history = True
            if self.delete_history:
                os.remove(self.resume_place_file)
        else:
            # No resume-info file exists; create an empty one:
            open(self.resume_place_file, 'a').close()
        
        if most_recently_sent is not None:
            print('Start emailing after address %s at %s' % (most_recently_sent, datetime.datetime.now()))
        else:
            print('Start emailing from the start of the address list %s' % datetime.datetime.now())
        
        try:
            self.login_sending()
                
            with open(self.email_addr_file, 'r') as fd:
                if most_recently_sent is not None:
                    # Find the most recently sent email
                    # in the mail file, and then continue
                    # from there:
                    while True:
                        email_addr = self.next_addr(fd)
                        if email_addr is None:
                            # All emails have been sent:
                            return True
                        if email_addr == most_recently_sent:
                            break

                # Get the first address to send:
                addr = self.next_addr(fd)
                if addr is None:
                    # All emails have been sent.
                    return True                        

                # Start sending. Go till either all 
                # emails are sent, or the SIGINT interrupt
                # service routine sets the end_bulk_mailer
                # flag:
                try:
                    while not self.end_bulk_mailer:
                        
                        # Did interrupt service indicate
                        # that we are to stop?
                        
                        if self.end_bulk_mailer:
                            print("Stop sending after '%s'" % addr)
                            
                        res = self.send_one(addr) # @UnusedVariable
                        
                        # We count even msgs that caused an
                        # error as 'sent', b/c this number is
                        # used to restart the relay service
                        # at the right spot in the email list
                        # after stopping. Error counts can be
                        # recovered from the log.
                        
                        self.num_sent += 1
                        if self.verbose and self.num_sent % REPORTING_INTERVAL == 0:
                            sys.stdout.write('Sent %s emails\r' % self.num_sent)
                            sys.stdout.flush()
                        
                        # Remember the address we just sent:
                        with open(self.resume_place_file,'w') as resume_fd:
                            resume_fd.write('%s,%s' % (addr,self.num_sent))
                            
                        batch_len += 1

                        # Get the next address to send:
                        addr = self.next_addr(fd)
                        if addr is None:
                            # All emails have been sent.
                            return True                        
                        
                        # Go more to send. Wait a bit so as not
                        # to overwhelm the server:
                        
                        self.wait_condition.acquire()
                        if batch_len >= self.batch_size:
                            
                            # Wait for inter_batch_delay minutes:
                            # The signal handler will 'notify()' this
                            # condition and yank us out, if a cnt-c
                            # is issued. 

                            self.wait_condition.wait(self.inter_batch_delay)
                            self.wait_condition.release()
                            batch_len = 0                         
                        else:
                            self.wait_condition.wait(self.inter_msg_delay)
                            self.wait_condition.release()                            
                        
                except IOError as e:
                    raise IOError('Trouble reading a line from the address file: %s (%s)' % (e.strerror, e.filename))
        finally:
            self.logout_sending()  

    def next_addr(self, email_file_fd):
        '''
        Given an open fd to the file that contains
        the email list, find the next email address,
        and return it. If the file is finished, return
        None. The method skips comments.
        
        @param email_file_fd: open file descriptor to the email list file.
        @type email_file_fd: file_descriptor
        @return: next email in the file, or None if file exhausted.
        @rtype: {None|str}
        '''

        addr = None
        while addr is None:

            # Get line from email addr file. Three
            # possible results: line could be 
            # empty string, which means the file is
            # exhausted. Or the line could be a comment,
            # or the line is a line containing the next
            # email addr:
            
            addr_line = email_file_fd.readline()
            if len(addr_line) == 0:
                # All emails have been sent.
                return None
    
            # Pick the email address out of the read line.
            # If we get None, the line was a comment. In 
            # that case, read next line:
            addr = self.isolate_email_addr(addr_line.strip())
            
        return addr
           
    def send_one(self, addr):
        '''
        Send one copy of the email to the
        given email address. If self.unit_test_case_obj is True,
        return the address without sending.
        
        @param addr: the email addr to which the email is to be sent.
        @type addr: string
        '''
        if self.unit_test_case_obj is not None:
            self.unit_test_case_obj.sending(addr)
            return
        msg = MIMEMultipart('alternative')
        msg.attach(MIMEText(self.body, 'plain', 'utf-8'))
        msg['From'] = FROM_ADDR
        msg['To'] = addr
        msg['Subject'] = 'Invitation to MOOC Enhancement Experiment (Phil Levis)'
        msg.add_header('reply-to', REPLY_TO)
        try:
            self.serverSending.sendmail(FROM_ADDR, [addr], msg.as_string())
            return True
        except SMTPServerDisconnected:
            pass
        except SMTPRecipientsRefused as e:
            print('Recipient refused: %s' % `e`)
            return False
        except Exception as e:
            print('Unexpected exception during send: %s' % `e`)
            return False
            
        # If we get here, SMTP server was disconnected.
        # Try again:
        print('Login back into SMTP server...')
        self.login_sending()
        try:
            self.serverSending.sendmail(FROM_ADDR, [addr], msg.as_string())
        except SMTPRecipientsRefused as e:
            print('Recipient refused: %s' % `e`)
            return False
        except Exception as e:
            print('Unexpected exception during send: %s' % `e`)
            return False
        print('...succeeded to send after login.')
        return True
         
    def login_sending(self):
        '''
        Login into sendmail server. But if self.unit_test_case_obj
        is True, do nothing.
        '''
        if self.unit_test_case_obj is not None:
            return
        self.serverSending = smtplib.SMTP(HOST2,587)
        #*********
        #self.serverSending.set_debuglevel(True)
        #*********
        self.serverSending.starttls()
        self.serverSending.login(USERNAME, self.imap_pwd)

    
    def logout_sending(self):
        '''
        Log out of the imap server. But if self.unit_test_case_obj
        is True, do nothing.
        '''
        if self.unit_test_case_obj is not None:
            return
        self.serverSending.quit()
        
    def shutdown(self):
        '''
        Catching cnt-c to stop email sending
        '''
        # Set flag that tells timer-controlled thread
        # to stop if it wakes up before we cancel
        # it in the next statement:
    
        self.end_bulk_mailer = True
        print('\nStopping bulk email sending on user request...')
        
        # Pull out of the sleep in the run() method:
        self.wait_condition.acquire()
        self.wait_condition.notify()
        self.wait_condition.release()
        
    def isolate_email_addr(self, addr_line):
        '''
        Given a line from the email addresses file,
        return the email address in the line, if it
        exists, else return None. Lines should be in
        any format like these:
        
            foo@bar.com
            foo@bar.com some other information
                  foo@bar.com some other information
            foo@bar.com,some other information
            foo@bar.com,    some other information
            # This is a comment
                    # This is a comment
        
        @param addr_line: line read from the file of email addresses to send to.
        @type addr_line: string
        @return: the email address or None
        @rtype: {None|string}
        
        '''
        
        if self.comment_pattern.search(addr_line) is not None:
            # Line is a comment
            return None
        
        addr_match = self.email_addr_pattern.search(addr_line)
        if addr_match is not None:
            return addr_match.group(1)
        
        return None

    def query_yes_no(self, question, default="yes"):
        '''
        Ask a yes/no question via raw_input() and return their answer.
    
        "question" is a string that is presented to the user.
        "default" is the presumed answer if the user just hits <Enter>.
            It must be "yes" (the default), "no" or None (meaning
            an answer is required of the user).
    
        The "answer" return value is True for "yes" or False for "no".
        '''
        
        valid = {"yes": True, "y": True, "ye": True,
                 "no": False, "n": False}
        if default is None:
            prompt = " [y/n] "
        elif default == "yes":
            prompt = " [Y/n] "
        elif default == "no":
            prompt = " [y/N] "
        else:
            raise ValueError("invalid default answer: '%s'" % default)
    
        while True:
            sys.stdout.write(question + prompt)
            choice = raw_input().lower()
            if default is not None and choice == '':
                return valid[default]
            elif choice in valid:
                return valid[choice]
            else:
                sys.stdout.write("Please respond with 'yes' or 'no' "
                                 "(or 'y' or 'n').\n")
    
def sigint_handler(the_signal, frame):
    if the_signal == signal.SIGINT:
        email_sender.shutdown()

if __name__ == '__main__':

    script_name = os.path.basename(sys.argv[0])
    usage = 'Usage: %s msg_body_file, email_addr_file' % script_name
    
    if len(sys.argv) != 3:
        print(usage)
        sys.exit(1)
    
    email_body_file = sys.argv[1]
    email_addr_file = sys.argv[2]
    
    # Register the cnt-c handler:
    signal.signal(signal.SIGINT, sigint_handler)
    
    email_sender = BulkMailer(email_body_file, email_addr_file)
    email_sender.start()
        
    email_sender.join()
    print('Sent %s emails.' % email_sender.num_sent)
        


    