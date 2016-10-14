
from util import *

def main():
    threading.Timer(5.0, main).start()
    unread_msgs,response = get_inbox(server1,server2)
    success=-1
    if response: success = run_script(unread_msgs,response)

    if success==1:
        for eid in unread_msgs:
            server1.store(eid, '+FLAGS', '\Seen')
    # server1.close()
    # server1.logout()
main()
