#!/usr/bin/env python

from threading import Lock
import threading

from util import EmailChecker


lock = Lock()

DONT_BLOCK = False

def main(num_server_contacts):

    # Called one more time:
    num_server_contacts += 1

    # If still working on previous call,
    # just return and let the next cycle
    # try again:
    
    #threading.Timer(30.0, main, [num_server_contacts]).start()
    threading.Timer(15.0, main, [num_server_contacts]).start()
    
    if not lock.acquire(DONT_BLOCK):
        return

    email_checker = EmailChecker()

    try:
        # Request new msgs from imap server, logging
        # the visit only every 10th time.
        (unread_msg_nums, response) = email_checker.get_inbox((num_server_contacts % 10) == 0)
    
        success=-1
        
        if response: 
            success = email_checker.pull_msgs(unread_msg_nums, response)
    
        if success==1:
            email_checker.mark_seen(unread_msg_nums)
    finally:
        email_checker.stop_logging()
        lock.release()

    # server1.close()
    # server1.logout()
    #server2.quit()

# Start main with zero-counter:
main(0)
