#!/usr/bin/env python

from util import *

def main(num_server_contacts):
    #threading.Timer(30.0, main, [num_server_contacts]).start()
    threading.Timer(15.0, main, [num_server_contacts]).start()
    server1,server2 = setup_servers()
    # Request new msgs from imap server, logging
    # the visit only every 10th time.
    num_server_contacts += 1
    unread_msgs,response = get_inbox(server1, 
                                     server2, 
                                     (num_server_contacts % 10) == 0
                                     )
    success=-1
    if response: success = run_script(unread_msgs,response,server1,server2)

    if success==1:
        for eid in unread_msgs:
            server1.store(eid, '+FLAGS', '\Seen')
    # server1.close()
    # server1.logout()
    #server2.quit()

# Start main with zero-counter:
main(0)
