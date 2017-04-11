#!/usr/bin/env python

import os
import signal
import sys
from threading import Lock
import threading

from util import EmailChecker
from bundlebuilder import usage


class EmailAnonServer(object):

    EMAIL_CHECK_INTERVAL = 15.0 # seconds
    # Used for non-blocking synch lock acquisition:
    DONT_BLOCK = False
    
    def __init__(self, pull_interval=None):
        '''
        Initialize the cyclical calling of the 
        imap-inbox checker.
        
        :param pull_interval: Number of seconds between each
                call to the imap server to check for new
                messages.
        :type pull_interval: float
        '''
    
        if pull_interval is None:
            EmailAnonServer.EMAIL_CHECK_INTERVAL = pull_interval
    
        # Flag for thread to stop checking for emails:
        self.stop_checking_email  = False
        
        # Register the cnt-c handler:
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # Number of times the IMAP server has
        # already been contacted. Incremented on each call. Used to
        # limit the number of "I read the inbox" log messages in calls
        # to get_inbox():
                
        self.num_server_contacts  = 0
        
        # For reentry prevention if pulling email
        # is slow, and the timer 'check-now' timer
        # fires before previous round is done:
        self.lock = Lock()
        
        # EmailChecker instance that does dirty
        # work of talking to the imap server:
        self.email_checker = EmailChecker()
    
        # Start recurring timer. Unit is seconds:
        self.check_timer = threading.Timer(EmailAnonServer.EMAIL_CHECK_INTERVAL, self.run_check)
        self.check_timer.start()
        
    def run_check(self):
        '''
        Called every EmailAnonServer.EMAIL_CHECK_INTERVAL seconds.
        Checks the imap box for new messages from students. 
        '''
        # Did a cnt-c SIGINT ask us to stop?
        if self.stop_checking_email:
            self.email_checker.log_program_stop()
            print('Stopped email checks on user request.')
            sys.exit()

        # If still working on previous call,
        # just return and let the next cycle
        # try again:
        
        if not self.lock.acquire(EmailAnonServer.DONT_BLOCK):
            return

        # Called one more time:
        self.num_server_contacts += 1
 
        try:
            # Request new msgs from imap server, logging
            # the visit only every 10th time.
            (unread_msg_nums, response) = self.email_checker.get_inbox((self.num_server_contacts % 100) == 0)
        
            success=-1
            
            #*************
            print('Puller was called.')
            return
            #*************
            
            if response: 
                success = self.email_checker.pull_msgs(unread_msg_nums, response)
        
            if success==1:
                self.email_checker.mark_seen(unread_msg_nums)
        finally:
            self.lock.release()
    
    def signal_handler(self, signal, frame):
        '''
        Catching cnt-c to stop checking email
        '''
        # Set flag that tells timer-controlled thread
        # to stop if it wakes up before we cancel
        # it in the next statement:
    
        self.stop_checking_email = True
        self.check_timer.cancel()
        self.email_checker.log_program_stop()
        self.email_checker.stop_logging()
        print('Stopped email checks on user request.')
        sys.exit(0)

if __name__ == '__main__':

    script_name = os.path.basename(sys.argv[0])
    usage = 'Usage: %s [mail-check-interval-in-secs]' % script_name
    
    if len(sys.argv) > 2:
        print(usage)
        sys.exit(0)
    
    check_interval = None
    if len(sys.argv) == 2:
        # Ensure that the given parameter is a number:
        try:
            check_interval = float(sys.argv[1])
        except ValueError:
            print(usage)
            sys.exit(1)
        
    EmailAnonServer(check_interval)
