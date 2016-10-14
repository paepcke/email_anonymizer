#!/usr/bin/env python
from util import *

def main():
    threading.Timer(30.0, main).start()
    server1,server2 = setup_servers()
    unread_msgs,response = get_inbox(server1,server2)
    success=-1
    if response: success = run_script(unread_msgs,response,server1,server2)

    if success==1:
        for eid in unread_msgs:
            server1.store(eid, '+FLAGS', '\Seen')
    # server1.close()
    # server1.logout()
    #server2.quit()
main()
