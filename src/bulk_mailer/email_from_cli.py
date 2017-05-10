#!/usr/bin/env python
'''
Created on May 10, 2017

@author: paepcke
'''
import argparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import shelve
from smtplib import SMTPServerDisconnected, SMTPRecipientsRefused
import smtplib
import sys


# The imap box:
HOST = 'cs-imap-x.stanford.edu' #MAIL Server hostname
HOST2 = 'cs.stanford.edu'
USERNAME = 'stats60' #Mailbox username
MAILBOX_EMAIL = 'stats60@cs.stanford.edu'
IMAP_PWD_FILE = 'imap_password.txt'          # File containing imap password in ~/.ssh

PREV_USER_INPUT_FILE = 'email_from_cli_prev_input'

class CLIEmailer(object):
    '''
    Sends one email with FROM/TO/Body provided
    interactively. Body may be in a file, or 
    is provided interactively when invoking this
    script
    '''

    def __init__(self, file_path=None):
        '''
        Constructor
        '''
        self.imap_pwd      = self.get_password_from_file()
        self.prior_parms   = shelve.open(PREV_USER_INPUT_FILE)
        
        self.solicit_email_info(file_path)
        
        # Update persistent prior parms:
        self.prior_parms['prior_from'] = self.from_addr
        self.prior_parms['prior_to'] = self.to_addr
        self.prior_parms['prior_return'] = self.reply_to_addr
        self.prior_parms['prior_subject'] = self.subject
        self.prior_parms['prior_body'] = self.body
        
#         print('From: %s' % self.from_addr)
#         print('To: %s' % self.to_addr)
#         print('Reply_to: %s' % self.reply_to_addr)
#         print('Subject: %s' % self.subject)
#         print('Body: %s' % self.body)
#         sys.exit(0)

        if self.send():
            print('Message sent.')
        else:
            print('Nothing sent.')
        
    def solicit_email_info(self, file_path=None):
        
        prior_from = prior_to = prior_return = prior_subject = prior_body = None
        
        # Read any inputs given during a previous invocation: 
        try:
            prior_from = self.prior_parms['prior_from']
        except:
            pass
        try:
            prior_to = self.prior_parms['prior_to']
        except:
            pass
        try:
            prior_return = self.prior_parms['prior_return']
        except:
            pass
        try:
            prior_subject = self.prior_parms['prior_subject']
        except:
            pass
        try:
            prior_body = self.prior_parms['prior_body']
        except:
            pass
        
        # If there were previous inputs, offer them if appropriate:
        if prior_from is not None and \
            prior_to is not None and \
            prior_return is not None and \
            prior_subject is not None and \
            prior_body is not None:
            try:
                use_all = self.query_yes_no('Use the previous message?')
            except KeyboardInterrupt:
                print("\nMessaging aborted; nothing sent.")
                sys.exit(0)

            # Init all from previous and return:                
            if use_all:
                self.from_addr = prior_from
                self.to_addr = prior_to
                self.reply_to_addr = prior_return
                self.subject = prior_subject
                self.body = prior_body
                return
        
        try:
            self.from_addr     = raw_input('From address' + ('(%s): '%prior_from if prior_from is not None else ': '))
            if len(self.from_addr) == 0:
                if prior_from is None:
                    raise ValueError("Must provide from-address.")
                else:
                    self.from_addr = prior_from
                    
            self.to_addr       = raw_input('To address' + ('(%s): '%prior_to if prior_to is not None else ': '))
            if len(self.to_addr) == 0:
                if prior_to is None:
                    raise ValueError("Must provide to-address.")
                else:
                    self.to_addr = prior_to
            
            reply_to_default = self.from_addr if prior_return is None else prior_return
            self.reply_to_addr = raw_input('Reply_to address (%s): ' % reply_to_default)
            if len(self.reply_to_addr) == 0:
                self.reply_to_addr = reply_to_default
            
            self.subject       = raw_input('Subject' + ('(%s): '%prior_subject if prior_to is not None else ': '))
            if len(self.subject) == 0:
                if prior_subject is None:
                    raise ValueError("Must provide a subject.")
                else:
                    self.subject = prior_subject
            
            use_prev_body = False
            if prior_body is not None:
                use_prev_body = self.query_yes_no('Use previous body?')

            if file_path is None:
                if not use_prev_body:
                    print('Enter message body; cnt-D at start of line when done:')
                    self.body = []
                    while True:
                        try:
                            line = raw_input("")
                        except EOFError:
                            break
                        self.body.append(line)
                    self.body = '\n'.join(self.body)
                else:
                    self.body = prior_body
            else:
                # Message body is a file
                self.body = self.body_from_file(file_path)
        except KeyboardInterrupt:
            print("\nMessaging aborted; nothing sent.")
            sys.exit(0)
            
    def send(self):
        '''
        Send one copy of the email. Expects the following
        to be initialized:
          - self.from_addr
          - self.to_addr
          - self.reply_to_addr
          - self.subject
          - self.body
        '''
        self.login_sending()
        
        try:
            msg = MIMEMultipart('alternative')
            msg.attach(MIMEText(self.body, 'plain', 'utf-8'))
            msg['From'] = self.from_addr
            msg['To'] = self.to_addr
            msg['Subject'] = self.subject
            msg.add_header('reply-to', self.reply_to_addr)
            try:
                self.serverSending.sendmail(self.from_addr, [self.to_addr], msg.as_string())
                return True
            except SMTPServerDisconnected:
                print("Could not log into imap server.")
                return False
            except SMTPRecipientsRefused as e:
                print('Recipient refused: %s' % `e`)
                return False
            except Exception as e:
                print('Unexpected exception during send: %s' % `e`)
                return False
            return True
        finally:
            self.logout_sending()
            
    def body_from_file(self, file_path):
        try:
            with open(file_path, 'r') as fd:
                body = fd.readlines()
        except IOError:
            print("Cannot read file '%s'; nothing sent." % file_path)
            sys.exit(1)
        return ''.join(body)
    
    def login_sending(self):
        '''
        Login into sendmail server.
        '''
        self.serverSending = smtplib.SMTP(HOST2,587)
        #*********
        #self.serverSending.set_debuglevel(True)
        #*********
        self.serverSending.starttls()
        self.serverSending.login(USERNAME, self.imap_pwd)
    
    def logout_sending(self):
        '''
        Log out of the imap server.
        '''
        self.serverSending.quit()
    

    def get_password_from_file(self):
        # Get mailbox password from ~/.ssh/imap_pwd.txt
        try:
            with open(os.path.join(os.getenv('HOME'), '.ssh', IMAP_PWD_FILE)) as fd:
                return fd.read().strip()
        except IOError:
            print('Cannot read pwd from ~/%s. Nothing sent.' % IMAP_PWD_FILE)
            sys.exit(1)
                
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
                
if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]), 
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-f', '--file',
                        default=None,
                        help="File name that contains the message body.\n" + \
                             "If not provided, enter body when prompted"
                        )
    
    args = parser.parse_args()
    CLIEmailer(args.file)