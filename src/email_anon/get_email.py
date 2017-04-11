#!/usr/bin/env python

import os
import signal
import sys
import threading

from util import EmailChecker
from bundlebuilder import usage


class EmailAnonServer(threading.Thread):

    # Default time in seconds to wait between
    # checking for new mail in the imap box.
    # Can be overriden by a command line argument,
    # and subsequent passing of the alternative
    # interval to the __init__() method:
    
    EMAIL_CHECK_INTERVAL = 15.0 # seconds
    
    def __init__(self, pull_interval=None):
        '''
        Initialize the cyclical calling of the 
        imap-inbox checker.
        
        :param pull_interval: Number of seconds between each
                call to the imap server to check for new
                messages.
        :type pull_interval: float
        '''
        super(EmailAnonServer, self).__init__()
 
        if pull_interval is not None:
            EmailAnonServer.EMAIL_CHECK_INTERVAL = pull_interval
    
        # Flag for thread to stop checking for emails:
        self.stop_checking_email  = False
        
        # Number of times the IMAP server has
        # already been contacted. Incremented on each call. Used to
        # limit the number of "I read the inbox" log messages in calls
        # to get_inbox():
                
        self.num_server_contacts  = 0
        
        # EmailChecker instance that does dirty
        # work of talking to the imap server:
        self.email_checker = EmailChecker()
        
        # Condition object for the run() method
        # to sleep on, while still having the 
        # ability to woken by the cnt-c signal
        # handler:
        
        self.wait_condition = threading.Condition()
        
        self.start()
            
    def run(self):
        '''
        Entered when this thread's 'start()' method is
        called. Checks the imap box for new messages from 
        students. Then uses a threading.condition object
        to sleep for EmailAnonServer.EMAIL_CHECK_INTERVAL
        seconds, unless the SIGINT handler wakes it earlier. 
        '''
        
        # Infinite loop; the self.stop_checking_email
        # flag can be set to stop this thread. That's
        # done, for example, in the SIGINT handler:
        
        while not self.stop_checking_email:
    
            self.wait_condition.acquire()
            
            # Called one more time:
            self.num_server_contacts += 1
            try:
                # Request new msgs from imap server, logging
                # the visit only every 10th time.
                (unread_msg_nums, response) = self.email_checker.get_inbox((self.num_server_contacts % 100) == 0)
             
                success=-1
                if response: 
                    success = self.email_checker.pull_msgs(unread_msg_nums, response)
             
                if success==1:
                    self.email_checker.mark_seen(unread_msg_nums)
                    
            # Make sure we keep running!
            except Exception as e:
                self.email_checker.logErr('Error during mail check: %s' % `e`)
                
            # Wait till it's time again to check.
            # The signal handler will 'notify()' this
            # condition and yank us out, if a cnt-c
            # is issued. 

            self.wait_condition.wait(EmailAnonServer.EMAIL_CHECK_INTERVAL)
            self.wait_condition.release()
        print("Mail checker is stopped.")
            
    def stop_email_check(self):
        '''
        Catching cnt-c to stop checking email
        '''
        # Set flag that tells timer-controlled thread
        # to stop if it wakes up before we cancel
        # it in the next statement:
    
        self.stop_checking_email = True
        # Write the 'interrupted by user' to the log:
        self.email_checker.log_program_stop()
        self.email_checker.stop_logging()
        print('\nStopping email checks on user request...')
        # Pull out of the sleep in the run() method:
        self.wait_condition.acquire()
        self.wait_condition.notify()
        self.wait_condition.release()
    
    
def sigint_handler(the_signal, frame):
    if the_signal == signal.SIGINT:
        email_checker.stop_email_check()
    
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

    # Register the cnt-c handler:
    signal.signal(signal.SIGINT, sigint_handler)
        
    # Start recurring timer. Unit is seconds:
    email_checker = EmailAnonServer(check_interval)
    
    while not email_checker.stop_checking_email:
        # Main thread: sleep till any signal arrives
        signal.pause()
    