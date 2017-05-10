#!/usr/bin/env python
'''
Created on May 10, 2017

@author: paepcke
'''
import argparse
import os
import sys

# The imap box:
HOST = 'cs-imap-x.stanford.edu' #MAIL Server hostname
HOST2 = 'cs.stanford.edu'
USERNAME = 'stats60' #Mailbox username
MAILBOX_EMAIL = 'stats60@cs.stanford.edu'
IMAP_PWD_FILE = 'imap_password.txt'          # File containing imap password in ~/.ssh

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
        self.imap_pwd = self.get_password_from_file()
        print("imappwd: '%s'" % self.imap_pwd)
        
        self.solicit_email_info(file_path)
        
        print('From: %s' % self.from_addr)
        print('To: %s' % self.to_addr)
        print('Body: %s' % self.body)
        #self.send()
        
    def solicit_email_info(self, file_path=None):
        try:
            self.from_addr = raw_input('From address: ')
            self.to_addr   = raw_input('To address: ')
            if file_path is None:
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
                # Message body is a file
                self.body = self.body_from_file(file_path)
        except KeyboardInterrupt:
            print("\nMessaging aborted; nothing sent.")
            sys.exit(0)
            
    def body_from_file(self, file_path):
        try:
            with open(file_path, 'r') as fd:
                body = fd.readlines()
        except IOError:
            print("Cannot read file '%s'; nothing sent." % file_path)
            sys.exit(1)
        return ''.join(body)

    def get_password_from_file(self):
        # Get mailbox password from ~/.ssh/imap_pwd.txt
        try:
            with open(os.path.join(os.getenv('HOME'), '.ssh', IMAP_PWD_FILE)) as fd:
                return fd.read().strip()
        except IOError:
            print('Cannot read pwd from ~/%s. Nothing sent.' % IMAP_PWD_FILE)
            sys.exit(1)
                
                
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