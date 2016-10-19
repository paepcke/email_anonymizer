#!/usr/bin/env python

from decimal import threading

from util import *


def main(num_server_contacts):

    #threading.Timer(30.0, main, [num_server_contacts]).start()
    threading.Timer(15.0, main, [num_server_contacts]).start()

    email_checker = EmailChecker()

    # Request new msgs from imap server, logging
    # the visit only every 10th time.

    num_server_contacts += 1
    (unread_msgs, response) = email_checker.get_inbox((num_server_contacts % 10) == 0)

    success=-1
    if response: 
        success = email_checker.run_script(unread_msgs, response)

    if success==1:
        email_checker.markSeen(unread_msgs)

    # server1.close()
    # server1.logout()
    #server2.quit()

# Start main with zero-counter:
main(0)
